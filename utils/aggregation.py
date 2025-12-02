# utils/aggregation.py — SAFE VERSION FOR FULL DATASET
import pandas as pd
import numpy as np


# ----------------------------------------------------------
# INTERNAL SAFETY CHECK
# ----------------------------------------------------------
def _missing(df, cols):
    return any(c not in df.columns for c in cols)


# ----------------------------------------------------------
# CORE PANEL COMPUTATION (NOW SAFE)
# ----------------------------------------------------------
def compute_panel(qdf, cat_id, group_cols):

    # 0 — Empty input
    if qdf is None or qdf.empty:
        return pd.DataFrame()

    # 1 — Required columns check
    required = [
        "BreakOutCategoryID", "Sample_Size",
        "Locationabbr", "Response"
    ]

    if _missing(qdf, required):
        return pd.DataFrame()

    # 2 — Select category
    df = qdf[qdf["BreakOutCategoryID"] == cat_id].copy()
    if df.empty:
        return pd.DataFrame()

    # 3 — DATA VALUE COLUMN (very important)
    if "Data_Value" in df.columns:
        val = "Data_Value"
    elif "Data_value" in df.columns:
        val = "Data_value"
    else:
        return pd.DataFrame()

    # Convert numerics
    df["Sample_Size"] = pd.to_numeric(df["Sample_Size"], errors="coerce")
    df[val] = pd.to_numeric(df[val], errors="coerce")

    # Remove missing
    df = df.dropna(subset=["Sample_Size", val])
    if df.empty:
        return pd.DataFrame()

    # Remove national rows
    df = df[~df["Locationabbr"].isin(["US", "UW"])]
    if df.empty:
        return pd.DataFrame()

    # 4 — If grouping depends on a missing col → stop
    if _missing(df, group_cols):
        return pd.DataFrame()

    # 5 — Weight/variance calculation
    df["persons"] = df["Sample_Size"]
    # avoid division-by-zero
    df = df[df[val] != 0]
    if df.empty:
        return pd.DataFrame()

    df["true_ss"] = df["persons"] * 100 / df[val]

    # 6 — Aggregate
    group = df.groupby(group_cols + ["Response"]).agg(
        persons_sum=("persons", "sum"),
        ss_sum=("true_ss", "sum")
    ).reset_index()

    # Remove invalid
    group = group[(group["persons_sum"] > 0) & (group["ss_sum"] > 0)]
    if group.empty:
        return pd.DataFrame()

    # 7 — Percent + Confidence Intervals
    group["percent"] = group["persons_sum"] * 100 / group["ss_sum"]

    # Standard error (safe)
    group["sdev"] = np.sqrt(
        (group["percent"] * (100 - group["percent"])) /
        np.maximum(group["ss_sum"], 1)
    )

    group["ci_low"] = group["percent"] - 2 * group["sdev"]
    group["ci_high"] = group["percent"] + 2 * group["sdev"]

    # Clean
    group = group.replace([np.inf, -np.inf], np.nan).dropna(subset=["percent"])

    return group


# ----------------------------------------------------------
# PANEL WRAPPERS (now safe)
# ----------------------------------------------------------
def aggregate_overall(qdf):
    return compute_panel(qdf, "CAT1", [])


def aggregate_gender(qdf):
    return compute_panel(qdf, "CAT2", ["Break_Out"])


def aggregate_age(qdf):
    return compute_panel(qdf, "CAT3", ["Break_Out"])


def aggregate_race(qdf):
    return compute_panel(qdf, "CAT4", ["Break_Out"])


def aggregate_education(qdf):
    return compute_panel(qdf, "CAT5", ["Break_Out"])


def aggregate_income(qdf):
    return compute_panel(qdf, "CAT6", ["Break_Out"])


def aggregate_temporal(qdf):
    return compute_panel(qdf, "CAT1", ["Year"])


def aggregate_state(qdf):
    return compute_panel(qdf, "CAT1", ["Locationabbr"])
