# BRFSS Interactive Dashboard (2011–present)

An interactive Plotly Dash app for exploring the CDC's **Behavioral Risk Factor Surveillance System**
(BRFSS) prevalence data. Pick any survey question, then see how responses break down by gender, age,
race, education, income, year and state, with confidence intervals on every estimate.

**Live: [brfssdashanalysis.vercel.app](https://brfssdashanalysis.vercel.app/)**

<p align="center"><img src="docs/dashboard.png" alt="Dashboard showing 'Ever told you that you have a form of depression?' — an overall figure of 17.0% with its confidence interval, a trend sparkline, and dot-and-interval breakdowns by gender and age group" width="100%"></p>
<p align="center"><sub>Every breakdown for one question on a single screen, from the full 2011–present CDC file.</sub></p>

## What it does

- **Question picker:** a three-level cascade of Class → Topic → Question (for example, Chronic Health Indicators → Depression).
- **One screen per question:** an overall figure, a year-by-year trend, breakdowns by gender, age, race, education and income, and a state map — all visible together, no tab-hopping.
- **One response at a time:** pick which answer to read. Most questions are yes/no, where drawing both at once spends four-fifths of the ink on the complement of what you asked.
- **Visible confidence intervals:** each estimate is a dot with its 95% interval drawn through it, on an axis framed to the data. Three quarters of the intervals in this dataset are under one percentage point wide, so a 0–100 axis hides them entirely.
- **Sorted, labelled groups:** every group carries its value, ordered by size, so the ranking is readable without counting gridlines.
- **Top / bottom 3:** narrow any breakdown to its three highest or lowest groups.

## How the numbers are computed

BRFSS publishes a prevalence percentage and a sample size per state, year and breakout group, not raw
responses. To pool states into one estimate, each panel:

1. Drops the national rows (`US`, `UW`) so states aren't double-counted.
2. Rebuilds each row's denominator from `Sample_Size × 100 / Data_value`.
3. Pools respondents and denominators across states, so `percent = Σ respondents / Σ denominators`.
4. Computes `SE = √(p(100 − p) / n)` and plots `p ± 2·SE`.

First, `utils/merges.py` maps older and alternative response and breakout codes onto one set (for
example, income brackets refined over the years), so a group means the same thing in every year.

## Run it

The repo ships with everything the dashboard needs, so a clone runs as-is:

```bash
python -m pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:8050](http://127.0.0.1:8050). Startup is instant: the app reads
`data/panels.json` (0.68 MB of pre-computed results) and nothing else. It does not import
pandas, numpy or pyarrow at all.

### Rebuilding the data

`data/panels.json` is generated. You only need to regenerate it if you change the
statistics or the CDC publishes a new year.

```bash
python -m pip install -r requirements-dev.txt
python -m pipeline.build --verify
```

That reads `data/brfss_raw.parquet` (21 MB, committed), applies the merges, pools the
states and writes `data/panels.json`. `--verify` re-runs the original per-question code in
`utils/` over every question and asserts the two agree, so the fast path can't silently
drift from the reference implementation.

To start from a fresh CDC download instead:

```bash
python -m pipeline.build --from-csv path/to/BRFSS_prevalence.csv --verify
```

The [CDC prevalence CSV](https://data.cdc.gov/api/views/dttw-5yxu/rows.csv?accessType=DOWNLOAD)
is about 1 GB; `--from-csv` converts it to the raw parquet first. Raw CSVs are git-ignored.

## Deploying

The dashboard runs on Vercel as a single Python serverless function, deployed from
`main` at [brfssdashanalysis.vercel.app](https://brfssdashanalysis.vercel.app/).
Pushing to `main` redeploys it.

```bash
vercel deploy
```

`api/index.py` exposes the Dash app's underlying Flask server, which is the WSGI callable
Vercel's Python runtime looks for, and `vercel.json` rewrites every path to it. The
pre-aggregation is what makes this viable: with only `dash` and `plotly` in
`requirements.txt` the bundle stays far inside Vercel's 250 MB function limit, and a cold
start loads a sub-megabyte JSON file instead of a 1 GB survey file.

`.vercelignore` keeps the parquet files, the pipeline and the coursework out of the
deployment.

## Structure

| Path | What it does |
|---|---|
| `app.py` | Layout, the question cascade, and one callback per panel |
| `assets/style.css` | Design tokens, card grid and responsive breakpoints |
| `api/index.py` | Vercel entry point — exposes the Flask server |
| `vercel.json` | Function config and catch-all rewrite |
| `pipeline/build.py` | Normalises the survey file and pre-computes every panel |
| `data/brfss_raw.parquet` | The CDC file as parquet, 21 MB (committed) |
| `data/panels.json` | Pre-aggregated results the app actually reads, 0.68 MB |
| `utils/merges.py` | Harmonises response and breakout IDs across years |
| `utils/prepare.py` · `utils/options.py` · `utils/aggregation.py` | The original per-question implementation, now the reference `--verify` checks the pipeline against |
| `BRFSS_Dashboard_Workflow_Notebook.ipynb` | Design rationale and workflow |
| `BRFSS_Dashboard_Slides.pptx` | Presentation |

## Stack

Python · Plotly Dash (runtime) · pandas · NumPy · PyArrow (build) · Vercel
