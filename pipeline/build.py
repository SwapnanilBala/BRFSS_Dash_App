"""Build the dashboard's runtime artifacts from the CDC BRFSS prevalence data.

Everything expensive happens here, once, so the deployed app never touches the
raw survey file. Three stages:

    normalize   data/brfss_raw.parquet   -> data/brfss_clean.parquet
    aggregate   data/brfss_clean.parquet -> data/panels.json
    index       data/brfss_clean.parquet -> folded into data/panels.json

Stage 0 (``--from-csv``) converts a fresh CDC download into the raw parquet.
The CDC refreshes this dataset about once a year, so this is not a hot path.

    python -m pipeline.build                  # normalize + aggregate + index
    python -m pipeline.build --verify         # also re-check against utils/
    python -m pipeline.build --from-csv PATH  # start from a fresh CDC download

The aggregation mirrors utils/aggregation.py exactly, but groups every question
in one pass instead of filtering the frame once per question. ``--verify``
proves the two agree.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.merges import apply_all_merges

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

RAW = DATA / "brfss_raw.parquet"
CLEAN = DATA / "brfss_clean.parquet"
PANELS_JSON = DATA / "panels.json"

# The only columns any panel or the question cascade reads. Everything else in
# the CDC file (footnotes, display order, geolocation) is dead weight here.
COLUMNS = [
    "Year",
    "Locationabbr",
    "Locationdesc",
    "Class",
    "Topic",
    "Question",
    "Response",
    "Break_Out",
    "Sample_Size",
    "Data_value",
    "BreakoutID",
    "BreakOutCategoryID",
    "ResponseID",
]

# panel name -> (BreakOutCategoryID, extra group columns)
# Matches the aggregate_* wrappers at the bottom of utils/aggregation.py.
PANELS: dict[str, tuple[str, list[str]]] = {
    "overall": ("CAT1", []),
    "gender": ("CAT2", ["Break_Out"]),
    "age": ("CAT3", ["Break_Out"]),
    "race": ("CAT4", ["Break_Out"]),
    "education": ("CAT5", ["Break_Out"]),
    "income": ("CAT6", ["Break_Out"]),
    "temporal": ("CAT1", ["Year"]),
    "state": ("CAT1", ["Locationabbr"]),
}

NATIONAL = ["US", "UW"]


# ---------------------------------------------------------------- stage 0


def from_csv(csv_path: Path) -> None:
    """Convert a fresh ~1 GB CDC download into the raw parquet."""
    print(f"[csv] reading {csv_path} (this takes a while)")
    df = pd.read_csv(csv_path, low_memory=False)
    print(f"[csv] {len(df):,} rows, {len(df.columns)} columns")
    DATA.mkdir(exist_ok=True)
    df.to_parquet(RAW, index=False, compression="zstd")
    print(f"[csv] wrote {RAW.name} ({RAW.stat().st_size / 1e6:.1f} MB)")


# ---------------------------------------------------------------- stage 1


def normalize() -> pd.DataFrame:
    """Apply the merges and row filters once, for the whole dataset.

    utils/prepare.load_question does this per question. Every step is row-wise,
    so hoisting it out of the request path changes nothing about the result.
    """
    print(f"[normalize] reading {RAW.name}")
    df = pd.read_parquet(RAW, columns=COLUMNS)
    print(f"[normalize] {len(df):,} rows in")

    df["Sample_Size"] = pd.to_numeric(df["Sample_Size"], errors="coerce")
    df["Data_value"] = pd.to_numeric(df["Data_value"], errors="coerce")

    df = apply_all_merges(df)

    # Drop the national aggregate rows so pooling states can't double-count.
    df = df[~df["Locationabbr"].isin(NATIONAL)]

    # compute_panel discards these rows anyway; doing it here shrinks the
    # intermediate and keeps the group-by pass honest.
    df = df.dropna(subset=["Sample_Size", "Data_value"])
    df = df[df["Data_value"] != 0]

    print(f"[normalize] {len(df):,} rows out")
    df.to_parquet(CLEAN, index=False, compression="zstd")
    print(f"[normalize] wrote {CLEAN.name} ({CLEAN.stat().st_size / 1e6:.1f} MB)")
    return df


# ---------------------------------------------------------------- stage 2


def compute_panel_all(df: pd.DataFrame, cat_id: str, group_cols: list[str]) -> pd.DataFrame:
    """Pooled prevalence and CIs for one panel, for every question at once.

    Identical arithmetic to utils.aggregation.compute_panel; "Question" simply
    joins the group keys, which is what filtering to one question did before.
    """
    sub = df[df["BreakOutCategoryID"] == cat_id]
    if sub.empty:
        return pd.DataFrame()

    # Rebuild each row's denominator from the published percentage, then pool
    # respondents and denominators across states.
    true_ss = sub["Sample_Size"] * 100 / sub["Data_value"]

    keys = ["Question"] + group_cols + ["Response"]
    group = (
        sub.assign(persons=sub["Sample_Size"], true_ss=true_ss)
        .groupby(keys, observed=True)
        .agg(persons_sum=("persons", "sum"), ss_sum=("true_ss", "sum"))
        .reset_index()
    )

    group = group[(group["persons_sum"] > 0) & (group["ss_sum"] > 0)]
    if group.empty:
        return pd.DataFrame()

    group["percent"] = group["persons_sum"] * 100 / group["ss_sum"]
    sdev = np.sqrt(
        (group["percent"] * (100 - group["percent"])) / np.maximum(group["ss_sum"], 1)
    )
    group["ci_low"] = group["percent"] - 2 * sdev
    group["ci_high"] = group["percent"] + 2 * sdev

    group = group.replace([np.inf, -np.inf], np.nan).dropna(subset=["percent"])
    return group


def aggregate(df: pd.DataFrame) -> tuple[dict, dict]:
    """Every panel for every question, plus the Class -> Topic -> Question tree."""
    # Short synthetic ids keep the JSON small. Keyed on question *text*, which
    # is what the app's dropdowns have always selected on.
    questions = sorted(df["Question"].dropna().unique().tolist())
    qid = {q: f"q{i}" for i, q in enumerate(questions)}
    print(f"[aggregate] {len(questions):,} distinct questions")

    panels: dict[str, dict[str, list]] = {i: {} for i in qid.values()}

    for name, (cat_id, group_cols) in PANELS.items():
        out = compute_panel_all(df, cat_id, group_cols)
        if out.empty:
            print(f"[aggregate] {name:<10} no rows")
            continue

        group_col = group_cols[0] if group_cols else None
        for question, chunk in out.groupby("Question", observed=True):
            rows = []
            for rec in chunk.itertuples(index=False):
                group = "" if group_col is None else getattr(rec, group_col)
                rows.append(
                    [
                        str(group),
                        str(rec.Response),
                        round(float(rec.percent), 2),
                        round(float(rec.ci_low), 2),
                        round(float(rec.ci_high), 2),
                    ]
                )
            panels[qid[question]][name] = rows

        print(f"[aggregate] {name:<10} {len(out):,} rows")

    # Cascade: the distinct (Class, Topic, Question) triples, as the dropdowns
    # walk them. A question reused under two topics shares one id and one set
    # of panel data, exactly as filtering on text did before.
    tree: dict[str, dict[str, list]] = {}
    triples = df[["Class", "Topic", "Question"]].dropna().drop_duplicates()
    for rec in triples.itertuples(index=False):
        bucket = tree.setdefault(rec.Class, {}).setdefault(rec.Topic, [])
        entry = {"id": qid[rec.Question], "text": rec.Question}
        if entry not in bucket:
            bucket.append(entry)

    for topics in tree.values():
        for questions_under_topic in topics.values():
            questions_under_topic.sort(key=lambda e: e["text"])

    index = {
        "classes": {
            c: dict(sorted(topics.items())) for c, topics in sorted(tree.items())
        }
    }
    return panels, index


def state_names(df: pd.DataFrame) -> dict[str, str]:
    """Locationabbr -> Locationdesc, so the map can label a state in words.

    The CDC file already pairs each code with its full name, including the
    territories, so there is nothing to hardcode here.
    """
    pairs = df[["Locationabbr", "Locationdesc"]].dropna().drop_duplicates()
    names = dict(zip(pairs["Locationabbr"], pairs["Locationdesc"]))

    ambiguous = len(pairs) - len(names)
    if ambiguous:
        print(f"[states] warning: {ambiguous} codes map to more than one name")

    print(f"[states] {len(names)} location codes named")
    return dict(sorted(names.items()))


def write_json(panels: dict, index: dict, states: dict, source_rows: int) -> None:
    payload = {
        "generated": date.today().isoformat(),
        "source_rows": source_rows,
        # [group, response, percent, ci_low, ci_high]; group is "" for overall
        "columns": ["group", "response", "percent", "ci_low", "ci_high"],
        "index": index,
        "states": states,
        "panels": panels,
    }
    PANELS_JSON.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    size = PANELS_JSON.stat().st_size
    filled = sum(1 for p in panels.values() if p)
    total = sum(len(rows) for p in panels.values() for rows in p.values())
    print(f"[write] {PANELS_JSON.name}: {size / 1e6:.2f} MB")
    print(f"[write] {filled:,}/{len(panels):,} questions with data, {total:,} result rows")


# ---------------------------------------------------------------- verify


def verify(df: pd.DataFrame, panels: dict, sample: int | None = None) -> bool:
    """Re-run the original per-question code and compare, question by question.

    ``sample`` limits the check to that many questions, spread across the list;
    the default checks all of them.
    """
    from utils.aggregation import (
        aggregate_age,
        aggregate_education,
        aggregate_gender,
        aggregate_income,
        aggregate_overall,
        aggregate_race,
        aggregate_state,
        aggregate_temporal,
    )
    from utils.prepare import load_question

    originals = {
        "overall": (aggregate_overall, None),
        "gender": (aggregate_gender, "Break_Out"),
        "age": (aggregate_age, "Break_Out"),
        "race": (aggregate_race, "Break_Out"),
        "education": (aggregate_education, "Break_Out"),
        "income": (aggregate_income, "Break_Out"),
        "temporal": (aggregate_temporal, "Year"),
        "state": (aggregate_state, "Locationabbr"),
    }

    raw = pd.read_parquet(RAW, columns=COLUMNS)
    questions = sorted(df["Question"].dropna().unique().tolist())
    qid = {q: f"q{i}" for i, q in enumerate(questions)}

    if sample is None:
        picks = questions
    else:
        # Spread the sample across the question list rather than taking the head.
        step = max(1, len(questions) // sample)
        picks = questions[::step][:sample]

    ok = True
    for question in picks:
        qdf = load_question(raw, question)
        for name, (fn, group_col) in originals.items():
            want = fn(qdf)
            got = panels[qid[question]].get(name, [])

            if want.empty:
                if got:
                    print(f"[verify] FAIL {name} / {question[:48]!r}: pipeline has rows, original none")
                    ok = False
                continue

            expected = {
                (
                    "" if group_col is None else str(r[group_col]),
                    str(r["Response"]),
                ): round(float(r["percent"]), 2)
                for _, r in want.iterrows()
            }
            actual = {(r[0], r[1]): r[2] for r in got}

            if expected.keys() != actual.keys():
                diff = set(expected) ^ set(actual)
                print(f"[verify] FAIL {name} / {question[:48]!r}: {len(diff)} key diffs")
                ok = False
                continue

            for key, value in expected.items():
                if abs(value - actual[key]) > 0.01:
                    print(f"[verify] FAIL {name} / {question[:48]!r} {key}: {value} vs {actual[key]}")
                    ok = False
                    break

    print(f"[verify] {'all panels match' if ok else 'MISMATCHES FOUND'} across {len(picks)} questions")
    return ok


# ---------------------------------------------------------------- cli


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the BRFSS dashboard artifacts.")
    ap.add_argument("--from-csv", type=Path, metavar="PATH", help="convert a fresh CDC download first")
    ap.add_argument("--verify", action="store_true", help="re-check every question against utils/")
    ap.add_argument("--verify-sample", type=int, metavar="N", help="limit --verify to N questions")
    ap.add_argument("--reuse-clean", action="store_true", help="skip normalize, read data/brfss_clean.parquet")
    args = ap.parse_args()

    if args.from_csv:
        from_csv(args.from_csv)

    if not RAW.is_file():
        print(f"error: {RAW} not found. Pass --from-csv with the CDC download.", file=sys.stderr)
        return 1

    if args.reuse_clean and CLEAN.is_file():
        print(f"[normalize] reusing {CLEAN.name}")
        df = pd.read_parquet(CLEAN)
    else:
        df = normalize()

    panels, index = aggregate(df)
    write_json(panels, index, state_names(df), source_rows=len(df))

    if args.verify and not verify(df, panels, sample=args.verify_sample):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
