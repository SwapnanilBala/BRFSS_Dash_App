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

QUESTION_TEXT = {
    q["id"]: q["text"]
    for topics in CLASSES.values()
    for questions in topics.values()
    for q in questions
}

# Half the questions end in the same parenthetical. Carrying it in the dropdown
# and the banner costs 53 characters on every one of them and says nothing that
# distinguishes one question from another, so it becomes a note instead. Doing
# this drops the median question from 94 characters to 57, and the longest from
# 172 to 117.
DERIVED_SUFFIX = "(variable calculated from one or more BRFSS questions)"
DERIVED_NOTE = "Derived variable, calculated from one or more BRFSS questions."


def _shorten(text):
    return text.replace(DERIVED_SUFFIX, "").strip().rstrip(",;")


QUESTION_SHORT = {qid: _shorten(t) for qid, t in QUESTION_TEXT.items()}
QUESTION_DERIVED = {
    qid: DERIVED_SUFFIX in t for qid, t in QUESTION_TEXT.items()
}

# Each row is [group, response, percent, ci_low, ci_high]; group is "" on the
# overall panel, a break-out label on the demographic ones, a year on the
# temporal panel and a state abbreviation on the map.
GROUP, RESPONSE, PERCENT, CI_LOW, CI_HIGH = range(5)

# The five demographic panels, shown together as small multiples.
BREAKDOWNS = [
    ("gender", "Gender"),
    ("age", "Age group"),
    ("race", "Race"),
    ("education", "Education"),
    ("income", "Income"),
]

FILTER_OPTIONS = [
    {"label": "All groups", "value": "all"},
    {"label": "Top 3", "value": "more"},
    {"label": "Bottom 3", "value": "less"},
]

# =========================================================
# PALETTE
# =========================================================
# One hue plus ink. These panels compare magnitude within a single response, so
# the colour job is sequential, not categorical — a colour per break-out group
# would imply a distinction that isn't in the data.
BLUE = "#2a78d6"
BLUE_FILL = "rgba(42,120,214,0.10)"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e6e5e1"
SURFACE = "#ffffff"
LAND = "#f0efec"
SEQUENTIAL = [[0.0, "#cde2fb"], [0.5, "#3987e5"], [1.0, "#104281"]]

FONT = "Inter, system-ui, -apple-system, sans-serif"

BASE_LAYOUT = dict(
    paper_bgcolor=SURFACE,
    plot_bgcolor=SURFACE,
    font=dict(family=FONT, size=13, color=INK),
    margin=dict(l=8, r=8, t=10, b=8),
    showlegend=False,
    hoverlabel=dict(font=dict(family=FONT, size=12)),
)

# Not "responsive": that makes dcc.Graph fill its container and ignore the
# figure's own height, which collapses these panels to a couple of pixels.
# Plotly's default autosize already tracks the container width.
GRAPH_CONFIG = {"displayModeBar": False}


# =========================================================
# DATA HELPERS
# =========================================================

def panel_rows(question_id, panel, response=None):
    if not question_id:
        return []
    rows = PANELS.get(question_id, {}).get(panel, [])
    if response is not None:
        rows = [r for r in rows if r[RESPONSE] == response]
    return rows


def responses_for(question_id):
    """Distinct responses for a question, in the order the panels list them."""
    seen = []
    for panel in ("overall", "age", "gender"):
        for row in panel_rows(question_id, panel):
            if row[RESPONSE] not in seen:
                seen.append(row[RESPONSE])
        if seen:
            break
    return seen


def default_response(question_id):
    """Prefer 'yes' where a question has one — it is the side being measured."""
    options = responses_for(question_id)
    if not options:
        return None
    for candidate in ("yes", "Yes"):
        if candidate in options:
            return candidate
    return options[0]


def apply_filter(rows, mode):
    if not rows or mode == "all":
        return rows
    ordered = sorted(rows, key=lambda r: r[PERCENT], reverse=(mode == "more"))
    return ordered[:3]


def axis_window(rows, pad=0.5):
    """Frame the axis on the data.

    Three quarters of the confidence intervals in this dataset are under one
    percentage point wide, so on a 0-100 axis they are smaller than a pixel.
    Zooming to the data is what makes them legible.
    """
    lows = [r[CI_LOW] for r in rows]
    highs = [r[CI_HIGH] for r in rows]
    lo, hi = min(lows), max(highs)
    span = max(hi - lo, 0.5)
    return [lo - span * pad, hi + span * pad]


# =========================================================
# FIGURE BUILDERS
# =========================================================

def empty_figure(message):
    fig = go.Figure()
    fig.add_annotation(
        text=message, showarrow=False,
        font=dict(family=FONT, size=13, color=MUTED),
        xref="paper", yref="paper", x=0.5, y=0.5,
    )
    fig.update_layout(
        **BASE_LAYOUT,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig


def build_dot_interval(rows, height):
    """A dot per group with its confidence interval drawn as a bar through it."""
    rows = sorted(rows, key=lambda r: r[PERCENT])
    labels = [r[GROUP] for r in rows]
    values = [r[PERCENT] for r in rows]

    fig = go.Figure()

    # Intervals first, so the dots and labels sit on top of them.
    for row in rows:
        fig.add_trace(go.Scatter(
            x=[row[CI_LOW], row[CI_HIGH]], y=[row[GROUP], row[GROUP]],
            mode="lines", line=dict(color=BLUE, width=3),
            opacity=0.30, hoverinfo="skip",
        ))

    fig.add_trace(go.Scatter(
        x=values, y=labels, mode="markers+text",
        marker=dict(size=11, color=BLUE, line=dict(width=2, color=SURFACE)),
        text=[f"{v:.1f}%" for v in values],
        textposition="middle right",
        textfont=dict(family=FONT, size=12, color=INK),
        customdata=[(r[CI_LOW], r[CI_HIGH]) for r in rows],
        hovertemplate=(
            "<b>%{y}</b><br>%{x:.2f}%<br>"
            "95% CI %{customdata[0]:.2f} – %{customdata[1]:.2f}<extra></extra>"
        ),
    ))

    fig.update_layout(
        # Bottom margin leaves room for the tick labels; without it the value
        # labels on a two-row panel sit on top of the axis.
        **{**BASE_LAYOUT, "margin": dict(l=8, r=8, t=6, b=26)}, height=height,
        xaxis=dict(
            range=axis_window(rows), showgrid=True, gridcolor=GRID,
            zeroline=False, ticksuffix="%",
            tickfont=dict(family=FONT, size=11, color=MUTED),
        ),
        yaxis=dict(
            showgrid=False, zeroline=False,
            tickfont=dict(family=FONT, size=12, color=INK),
        ),
    )
    return fig


def build_sparkline(rows, height):
    rows = sorted(rows, key=lambda r: int(r[GROUP]))
    fig = go.Figure(go.Scatter(
        x=[int(r[GROUP]) for r in rows],
        y=[r[PERCENT] for r in rows],
        mode="lines", line=dict(color=BLUE, width=2.5, shape="spline", smoothing=0.5),
        fill="tozeroy", fillcolor=BLUE_FILL,
        customdata=[(r[CI_LOW], r[CI_HIGH]) for r in rows],
        hovertemplate=(
            "<b>%{x}</b><br>%{y:.2f}%<br>"
            "95% CI %{customdata[0]:.2f} – %{customdata[1]:.2f}<extra></extra>"
        ),
    ))
    values = [r[PERCENT] for r in rows]
    fig.update_layout(
        **{**BASE_LAYOUT, "margin": dict(l=8, r=8, t=6, b=22)}, height=height,
        hovermode="x unified",
        xaxis=dict(showgrid=False, zeroline=False, dtick=2,
                   tickfont=dict(family=FONT, size=11, color=MUTED)),
        yaxis=dict(visible=False, range=[0, max(values) * 1.25]),
    )
    return fig


def build_map(rows, height):
    fig = go.Figure(go.Choropleth(
        locations=[r[GROUP] for r in rows],
        z=[r[PERCENT] for r in rows],
        locationmode="USA-states",
        colorscale=SEQUENTIAL,
        marker_line_color=SURFACE, marker_line_width=1,
        colorbar=dict(thickness=10, len=0.7, outlinewidth=0, ticksuffix="%",
                      tickfont=dict(family=FONT, size=11, color=MUTED)),
        customdata=[(r[CI_LOW], r[CI_HIGH]) for r in rows],
        hovertemplate=(
            "<b>%{location}</b><br>%{z:.2f}%<br>"
            "95% CI %{customdata[0]:.2f} – %{customdata[1]:.2f}<extra></extra>"
        ),
    ))
    fig.update_layout(
        **{**BASE_LAYOUT, "margin": dict(l=0, r=0, t=0, b=0)}, height=height,
        # Plotly fits the usa scope at about a third of the available area by
        # default, which leaves the map floating in the card; scale 1 fills it.
        geo=dict(scope="usa", bgcolor=SURFACE, lakecolor=SURFACE,
                 landcolor=LAND, subunitcolor=SURFACE,
                 projection=dict(scale=1.0)),
    )
    return fig


# =========================================================
# DASH APP
# =========================================================
app = Dash(__name__, title="BRFSS Interactive Dashboard")
server = app.server  # WSGI entry point for Vercel / gunicorn


def selector(label, component):
    return html.Div(className="selector", children=[
        html.Label(label, className="selector-label"),
        component,
    ])


def card(children, className="card"):
    return html.Div(className=className, children=children)


app.layout = html.Div(className="page", children=[

    html.Header(className="header", children=[
        html.H1("BRFSS Interactive Dashboard", className="title"),
        html.P(
            "CDC Behavioral Risk Factor Surveillance System, 2011–present. "
            "Every estimate is pooled across states and carries a 95% confidence interval.",
            className="subtitle",
        ),
    ]),

    # -------------------- QUESTION CASCADE --------------------
    # Questions run to 117 characters even with the boilerplate stripped, so
    # they get a row to themselves rather than a third of one.
    html.Div(className="selectors", children=[
        selector("Class", dcc.Dropdown(id="class-dd", options=[
            {"label": c, "value": c} for c in CLASSES
        ], placeholder="Select a class", clearable=False)),
        selector("Topic", dcc.Dropdown(
            id="topic-dd", placeholder="Select a topic", clearable=False)),
    ]),

    html.Div(className="selectors selectors-question", children=[
        selector("Question", dcc.Dropdown(
            id="question-dd", placeholder="Select a question", clearable=False)),
    ]),

    # The dropdown is a single line and still truncates the longest questions;
    # this is where the full text is always readable.
    html.Div(id="question-banner", className="question-banner hidden", children=[
        html.P(id="question-banner-text", className="question-banner-text"),
        html.P(id="question-banner-note", className="question-banner-note"),
    ]),

    # -------------------- RESPONSE + FILTER --------------------
    html.Div(id="controls", className="controls", children=[
        html.Div(className="control-group", children=[
            html.Span("Showing", className="control-label"),
            dcc.RadioItems(id="response-rd", className="chips", inline=True),
        ]),
        html.Div(className="control-group", children=[
            html.Span("Groups", className="control-label"),
            dcc.RadioItems(id="mode-rd", className="chips", options=FILTER_OPTIONS,
                           value="all", inline=True),
        ]),
    ]),

    # -------------------- EMPTY STATE --------------------
    html.Div(id="prompt", className="prompt", children=[
        html.P("Pick a class, topic and question above to see the breakdowns."),
    ]),

    # -------------------- RESULTS --------------------
    html.Div(id="results", className="results", children=[

        html.Div(className="grid grid-lead", children=[
            card([
                html.P(id="hero-caption", className="card-label"),
                html.P(id="hero-value", className="hero"),
                html.P(id="hero-ci", className="hero-ci"),
                html.P(id="hero-note", className="card-note"),
            ], className="card card-hero"),
            card([
                html.P("Trend, 2011–present", className="card-label"),
                dcc.Graph(id="temporal-plot", config=GRAPH_CONFIG),
            ], className="card card-trend"),
        ]),

        html.Div(className="grid grid-breakdowns", children=[
            card([
                html.P(label, className="card-label"),
                dcc.Graph(id=f"{panel}-plot", config=GRAPH_CONFIG),
            ])
            for panel, label in BREAKDOWNS
        ]),

        card([
            html.P(id="map-label", className="card-label"),
            dcc.Graph(id="state-plot", config=GRAPH_CONFIG),
        ]),
    ]),

    html.Footer(className="footer", children=[
        html.P([
            "Percentages are pooled across states: each row's denominator is rebuilt "
            "from the published prevalence, then respondents and denominators are "
            "summed. Intervals are ±2 standard errors.",
        ]),
    ]),
])


# =========================================================
# CASCADE CALLBACKS
# =========================================================

@app.callback(
    Output("topic-dd", "options"),
    Output("topic-dd", "value"),
    Input("class-dd", "value"),
)
def update_topics(selected_class):
    topics = list(CLASSES.get(selected_class, {}))
    return [{"label": t, "value": t} for t in topics], None


@app.callback(
    Output("question-dd", "options"),
    Output("question-dd", "value"),
    Input("class-dd", "value"),
    Input("topic-dd", "value"),
)
def update_questions(selected_class, selected_topic):
    questions = CLASSES.get(selected_class, {}).get(selected_topic, [])
    return [
        {"label": QUESTION_SHORT[q["id"]], "value": q["id"]} for q in questions
    ], None


@app.callback(
    Output("question-banner", "className"),
    Output("question-banner-text", "children"),
    Output("question-banner-note", "children"),
    Input("question-dd", "value"),
)
def update_question_banner(question_id):
    if not question_id:
        return "question-banner hidden", "", ""
    note = DERIVED_NOTE if QUESTION_DERIVED[question_id] else ""
    return "question-banner", QUESTION_SHORT[question_id], note


@app.callback(
    Output("response-rd", "options"),
    Output("response-rd", "value"),
    Input("question-dd", "value"),
)
def update_responses(question_id):
    options = responses_for(question_id)
    return (
        [{"label": r, "value": r} for r in options],
        default_response(question_id),
    )


@app.callback(
    Output("results", "className"),
    Output("prompt", "className"),
    Output("controls", "className"),
    Input("question-dd", "value"),
)
def toggle_sections(question_id):
    """Show the prompt until a question is chosen, then the results."""
    if question_id:
        return "results", "prompt hidden", "controls"
    return "results hidden", "prompt", "controls hidden"


# =========================================================
# HEADLINE
# =========================================================

@app.callback(
    Output("hero-value", "children"),
    Output("hero-ci", "children"),
    Output("hero-caption", "children"),
    Output("hero-note", "children"),
    Input("question-dd", "value"),
    Input("response-rd", "value"),
)
def update_hero(question_id, response):
    rows = panel_rows(question_id, "overall", response)
    if not rows:
        return "—", "", "Overall", "No overall estimate for this question."

    row = rows[0]
    states = len({r[GROUP] for r in panel_rows(question_id, "state", response)})
    return (
        f"{row[PERCENT]:.1f}%",
        f"95% CI {row[CI_LOW]:.1f} – {row[CI_HIGH]:.1f}",
        "Overall",
        f"Adults answering “{response}”, pooled across {states} reporting states.",
    )


# =========================================================
# PANEL CALLBACKS
# =========================================================
# Registered from BREAKDOWNS so the five small multiples cannot drift apart.

def register_breakdown(panel, label):
    @app.callback(
        Output(f"{panel}-plot", "figure"),
        Input("question-dd", "value"),
        Input("response-rd", "value"),
        Input("mode-rd", "value"),
    )
    def update_breakdown(question_id, response, mode, panel=panel, label=label):
        rows = apply_filter(panel_rows(question_id, panel, response), mode)
        if not rows:
            return empty_figure(f"No {label.lower()} breakdown for this question")
        # Roughly one row of height per group, so a two-group panel is not
        # stretched to the height of a six-group one. The floor keeps the two
        # -row panels tall enough that the value labels clear the axis.
        return build_dot_interval(rows, height=max(158, 34 * len(rows) + 62))

    return update_breakdown


for _panel, _label in BREAKDOWNS:
    register_breakdown(_panel, _label)


@app.callback(
    Output("temporal-plot", "figure"),
    Input("question-dd", "value"),
    Input("response-rd", "value"),
)
def update_temporal(question_id, response):
    rows = panel_rows(question_id, "temporal", response)
    if not rows:
        return empty_figure("No year-by-year data for this question")
    return build_sparkline(rows, height=150)


@app.callback(
    Output("state-plot", "figure"),
    Output("map-label", "children"),
    Input("question-dd", "value"),
    Input("response-rd", "value"),
)
def update_state(question_id, response):
    rows = panel_rows(question_id, "state", response)
    if not rows:
        return empty_figure("No state-level data for this question"), "By state"
    # Only the selected response is mapped, so every state is shaded on the
    # same quantity — unlike a "highest response per state" rule, which can
    # silently colour different states by different responses.
    return build_map(rows, height=420), f"By state · {len(rows)} reporting"


if __name__ == "__main__":
    app.run(debug=True)
