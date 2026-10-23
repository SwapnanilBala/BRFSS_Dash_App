import json
from pathlib import Path

from dash import Dash, dcc, html, Input, Output
import plotly.graph_objects as go

# =========================================================
# LOAD PRE-AGGREGATED PANELS
# =========================================================
# pipeline/build.py has already pooled every state, applied the code merges and
# computed the confidence intervals, so there is nothing to aggregate here: a
# panel is a dict lookup. That keeps this importable without pandas, numpy or
# pyarrow, which is what lets it fit in a serverless function.
PANELS_PATH = Path(__file__).resolve().parent / "data" / "panels.json"

if not PANELS_PATH.is_file():
    raise FileNotFoundError(
        f"Pre-aggregated panels not found: {PANELS_PATH}. "
        "Run `python -m pipeline.build` to generate them (see README.md)."
    )

with PANELS_PATH.open(encoding="utf-8") as fh:
    BUNDLE = json.load(fh)

PANELS = BUNDLE["panels"]
CLASSES = BUNDLE["index"]["classes"]

# question id -> question text, for the selected-question banner
QUESTION_TEXT = {
    q["id"]: q["text"]
    for topics in CLASSES.values()
    for questions in topics.values()
    for q in questions
}

# Each row is [group, response, percent, ci_low, ci_high]; group is "" on the
# overall panel, a break-out label on the demographic ones, a year on the
# temporal panel and a state abbreviation on the map.
GROUP, RESPONSE, PERCENT, CI_LOW, CI_HIGH = range(5)

# panel id -> (tab label, x-axis title)
TABS = [
    ("overall", "Overall", "Response"),
    ("gender", "Gender", "Gender"),
    ("age", "Age", "Age group"),
    ("race", "Race", "Race"),
    ("education", "Education", "Education"),
    ("income", "Income", "Income"),
    ("temporal", "Temporal", "Year"),
    ("state", "State / Territory Heatmap", "State"),
]

FILTER_OPTIONS = [
    {"label": "Show All", "value": "all"},
    {"label": "More (Top 3)", "value": "more"},
    {"label": "Less (Bottom 3)", "value": "less"},
]

EMPTY_TITLES = {
    "overall": "No aggregation possible",
    "gender": "No gender data",
    "age": "No age data",
    "race": "No race data",
    "education": "No education data",
    "income": "No income data",
    "temporal": "No temporal data",
    "state": "No state data",
}


# =========================================================
# HELPERS
# =========================================================

def apply_filter(rows, mode):
    if not rows:
        return rows
    if mode == "more":
        return sorted(rows, key=lambda r: r[PERCENT], reverse=True)[:3]
    if mode == "less":
        return sorted(rows, key=lambda r: r[PERCENT])[:3]
    return rows


def panel_rows(question_id, panel):
    if not question_id:
        return []
    return PANELS.get(question_id, {}).get(panel, [])


def build_ci_bar(rows, title, x_col, x_title, orientation="v"):
    """Grouped bars, one trace per response, with +/- 2 SE whiskers."""
    by_response = {}
    for row in rows:
        by_response.setdefault(row[RESPONSE], []).append(row)

    fig = go.Figure()
    for response, group_rows in by_response.items():
        labels = [str(r[x_col]) for r in group_rows]
        values = [r[PERCENT] for r in group_rows]
        error = dict(
            type="data",
            symmetric=False,
            array=[r[CI_HIGH] - r[PERCENT] for r in group_rows],
            arrayminus=[r[PERCENT] - r[CI_LOW] for r in group_rows],
        )
        bounds = [(r[CI_LOW], r[CI_HIGH]) for r in group_rows]
        label_axis, value_axis = ("y", "x") if orientation == "h" else ("x", "y")
        hover = (
            f"%{{{label_axis}}}<br>{response}<br>"
            f"%{{{value_axis}:.2f}}%<br>"
            "CI %{customdata[0]:.2f} – %{customdata[1]:.2f}<extra></extra>"
        )

        fig.add_trace(go.Bar(
            name=str(response),
            customdata=bounds,
            hovertemplate=hover,
            **(
                {"y": labels, "x": values, "orientation": "h", "error_x": error}
                if orientation == "h"
                else {"x": labels, "y": values, "error_y": error}
            ),
        ))

    if orientation == "h":
        fig.update_layout(barmode="group", title=title,
                          xaxis_title="Percent (%)", yaxis_title=x_title)
    else:
        fig.update_layout(barmode="group", title=title,
                          xaxis_title=x_title, yaxis_title="Percent (%)")
    return fig


def build_temporal_line(rows, title):
    by_response = {}
    for row in rows:
        by_response.setdefault(row[RESPONSE], []).append(row)

    fig = go.Figure()
    for response, group_rows in by_response.items():
        points = sorted(group_rows, key=lambda r: int(r[GROUP]))
        fig.add_trace(go.Scatter(
            name=str(response),
            x=[int(r[GROUP]) for r in points],
            y=[r[PERCENT] for r in points],
            mode="lines+markers",
        ))
    fig.update_layout(title=title, xaxis_title="Year", yaxis_title="Percent (%)")
    return fig


def build_geo_map(rows):
    """Option B — pick the HIGHEST RESPONSE per state."""
    if not rows:
        return go.Figure(layout={"title": "No state-level data available"})

    best = {}
    for row in sorted(rows, key=lambda r: r[PERCENT], reverse=True):
        state = row[GROUP]
        if len(state) == 2 and state not in best:  # keep only valid states
            best[state] = row

    if not best:
        return go.Figure(layout={"title": "No state-level data available"})

    states = list(best)
    fig = go.Figure(go.Choropleth(
        locations=states,
        locationmode="USA-states",
        z=[best[s][PERCENT] for s in states],
        text=[best[s][RESPONSE] for s in states],
        colorscale="Plasma",
        colorbar_title="Percent",
        hovertemplate="%{location}<br>%{text}<br>%{z:.2f}%<extra></extra>",
    ))
    fig.update_layout(
        geo_scope="usa",
        title="State-Level Prevalence (Highest Response per State)",
        margin={"l": 0, "r": 0, "t": 50, "b": 0},
    )
    return fig


# =========================================================
# DASH APP
# =========================================================
app = Dash(__name__)
server = app.server  # WSGI entry point for Vercel / gunicorn


def tab_body(panel):
    return [
        html.Br(),
        dcc.Dropdown(
            id=f"{panel}-filter",
            options=FILTER_OPTIONS,
            value="all",
            style={'width': '25%'}
        ),
        dcc.Graph(id=f"{panel}-plot")
    ]


app.layout = html.Div(style={'padding': '20px'}, children=[

    html.H1("BRFSS Interactive Dashboard"),

    # -------------------- TOP DROPDOWNS --------------------
    html.Div(style={'display': 'flex', 'gap': '15px'}, children=[
        dcc.Dropdown(
            id="class-dd",
            options=[{"label": c, "value": c} for c in CLASSES],
            placeholder="Select Class",
            style={'width': '30%'}
        ),
        dcc.Dropdown(
            id="topic-dd",
            placeholder="Select Topic",
            style={'width': '30%'}
        ),
        dcc.Dropdown(
            id="question-dd",
            placeholder="Select Question",
            style={'width': '40%'}
        ),
    ]),

    html.Div(
        id="selected-question-display",
        style={
            'marginTop':'20px',
            'fontSize':'20px',
            'fontWeight':'bold',
            'background':'#000',
            'color':'white',
            'padding':'10px',
            'borderRadius':'8px'
        }
    ),

    html.Hr(),

    # -------------------- TABS --------------------
    dcc.Tabs(id="tabs", children=[
        dcc.Tab(label=label, children=tab_body(panel))
        for panel, label, _ in TABS
    ])
])


# =========================================================
# DROPDOWN CASCADE CALLBACKS
# =========================================================

@app.callback(
    Output("topic-dd", "options"),
    Input("class-dd", "value")
)
def update_topics(c):
    return [{"label": t, "value": t} for t in CLASSES.get(c, {})]


@app.callback(
    Output("question-dd", "options"),
    Input("class-dd", "value"),
    Input("topic-dd", "value")
)
def update_questions(c, t):
    questions = CLASSES.get(c, {}).get(t, [])
    return [{"label": q["text"], "value": q["id"]} for q in questions]


@app.callback(
    Output("selected-question-display", "children"),
    Input("question-dd", "value")
)
def show_q(q):
    if not q:
        return "📌 No question selected"
    return f"📌 Selected Question: {QUESTION_TEXT.get(q, q)}"


# =========================================================
# PANEL CALLBACKS
# =========================================================
# One per tab, registered from TABS so the eight panels can't drift apart.

def register_panel(panel, x_title):
    @app.callback(
        Output(f"{panel}-plot", "figure"),
        Input("question-dd", "value"),
        Input(f"{panel}-filter", "value"),
    )
    def update_panel(question_id, mode, panel=panel, x_title=x_title):
        if not question_id:
            return go.Figure()

        rows = apply_filter(panel_rows(question_id, panel), mode)
        if not rows:
            return go.Figure(layout={"title": EMPTY_TITLES[panel]})

        if panel == "state":
            return build_geo_map(rows)
        if panel == "temporal":
            return build_temporal_line(rows, "Temporal Trend")
        if panel == "overall":
            return build_ci_bar(rows, "Overall Summary", RESPONSE, x_title)
        if panel == "gender":
            return build_ci_bar(rows, "By Gender", GROUP, x_title, orientation="h")
        return build_ci_bar(rows, f"By {x_title}", GROUP, x_title)

    return update_panel


for _panel, _label, _x_title in TABS:
    register_panel(_panel, _x_title)


if __name__ == "__main__":
    app.run(debug=True)
