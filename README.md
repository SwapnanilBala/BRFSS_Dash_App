# BRFSS Interactive Dashboard (2011–present)

An interactive Plotly Dash app for exploring the CDC's **Behavioral Risk Factor Surveillance System**
(BRFSS) prevalence data. Pick any survey question, then see how responses break down by gender, age,
race, education, income, year and state, with confidence intervals on every estimate.

<p align="center"><img src="docs/dashboard-age.png" alt="Dashboard showing 'Ever told you that you have a form of depression?' broken down by age group, with confidence-interval whiskers on each bar" width="100%"></p>
<p align="center"><sub>"Ever told you that you have a form of depression?" by age group, from the full 2011–present CDC file.</sub></p>

## What it does

- **Question picker:** a three-level cascade of Class → Topic → Question (for example, Chronic Health Indicators → Depression).
- **Eight panels:** Overall, Gender, Age, Race, Education, Income, a year-by-year trend, and a state/territory map. A panel with no data for the chosen question says so instead of drawing an empty chart.
- **Confidence intervals:** every bar carries ±2 standard-error whiskers, roughly a 95% interval.
- **Top / bottom 3:** each panel can be narrowed to the three highest or lowest groups.

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

The dashboard runs on Vercel as a single Python serverless function.

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
| `api/index.py` | Vercel entry point — exposes the Flask server |
| `vercel.json` | Function config and catch-all rewrite |
| `pipeline/build.py` | Normalises the survey file and pre-computes every panel |
| `data/brfss_raw.parquet` | The CDC file as parquet, 21 MB (committed) |
| `data/panels.json` | Pre-aggregated results the app actually reads, 0.68 MB |
| `utils/merges.py` | Harmonises response and breakout IDs across years |
| `utils/prepare.py` · `utils/options.py` · `utils/aggregation.py` | The original per-question implementation, now the reference `--verify` checks the pipeline against |
| `assets/style.css` | Dashboard styling |
| `BRFSS_Dashboard_Workflow_Notebook.ipynb` | Design rationale and workflow |
| `BRFSS_Dashboard_Slides.pptx` | Presentation |

## Stack

Python · Plotly Dash (runtime) · pandas · NumPy · PyArrow (build) · Vercel
