import json
from pathlib import Path

from dash import Dash, dcc, html, Input, Output, State
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

# Locationabbr -> full name, straight from the CDC file. The map is keyed on
# the two-letter code because that is what Plotly's USA-states mode needs, so
# this is what lets the hover say "Kentucky" rather than "KY".
STATE_NAMES = BUNDLE.get("states", {})

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

THEME_OPTIONS = [
    {"label": "System", "value": "system"},
    {"label": "Light", "value": "light"},
    {"label": "Dark", "value": "dark"},
]

# =========================================================
# PALETTE
# =========================================================
# One hue plus ink. These panels compare magnitude within a single response, so
# the colour job is sequential, not categorical — a colour per break-out group
# would imply a distinction that isn't in the data.
#
# Plotly takes its colours from here, not from the stylesheet, so a CSS theme
# can't reach the figures: every builder takes the resolved theme and the
# figure callbacks re-run when it changes. Dark is a selected palette rather
# than an inversion — the blue steps up to the dark-surface slot, gridlines
# drop to a hairline, and the map's ramp flips its anchor so low values recede
# toward the dark surface the way they recede toward white in light mode.
THEMES = {
    "light": dict(
        blue="#2a78d6",
        blue_fill="rgba(42,120,214,0.10)",
        interval_opacity=0.40,
        ink="#0b0b0b",
        muted="#52514e",
        grid="#e1e0d9",
        surface="#ffffff",
        land="#f0efec",
        # Plotly stretches the scale over the data's own range, so the low end
        # is the lowest reporting state, not zero — it has to stay visibly
        # coloured against the grey of states with no data. Step 250 is the
        # lightest that clears 2:1 on white.
        sequential=[[0.0, "#86b6ef"], [0.5, "#3987e5"], [1.0, "#104281"]],
        hover_bg="#ffffff",
        hover_line="#d6d5ce",
    ),
    "dark": dict(
        blue="#3987e5",
        blue_fill="rgba(57,135,229,0.16)",
        interval_opacity=0.50,
        ink="#f0efec",
        muted="#c3c2b7",
        grid="#2c2c2a",
        surface="#1a1a19",
        land="#383835",
        # Step 600 is the darkest a ramp may start on this surface and still
        # clear 2:1, so the lowest state never sinks into the background.
        sequential=[[0.0, "#184f95"], [0.5, "#3987e5"], [1.0, "#b7d3f6"]],
        hover_bg="#262624",
        hover_line="#383835",
    ),
}

FONT = "Inter, system-ui, -apple-system, sans-serif"

# Not "responsive": that makes dcc.Graph fill its container and ignore the
# figure's own height, which collapses these panels to a couple of pixels.
# Plotly's default autosize already tracks the container width.
GRAPH_CONFIG = {"displayModeBar": False}


def palette(theme):
    """The colours for a resolved theme; anything unresolved falls back to light."""
    return THEMES.get(theme, THEMES["light"])


def base_layout(p):
    return dict(
        paper_bgcolor=p["surface"],
        plot_bgcolor=p["surface"],
        font=dict(family=FONT, size=13, color=p["ink"]),
        margin=dict(l=8, r=8, t=10, b=8),
        showlegend=False,
        hoverlabel=dict(
            bgcolor=p["hover_bg"],
            bordercolor=p["hover_line"],
            font=dict(family=FONT, size=12, color=p["ink"]),
        ),
    )


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


def axis_window(rows, pad=0.12):
    """Frame the axis on the data, with just enough room for the dots.

    The value labels live in their own column outside the plot, so the axis
    no longer has to make room for them and every interval gets the width.
    """
    lows = [r[CI_LOW] for r in rows]
    highs = [r[CI_HIGH] for r in rows]
    lo, hi = min(lows), max(highs)
    span = max(hi - lo, 0.5)
    return [lo - span * pad, hi + span * pad]


def margin_text(row):
    """The 95% interval as a ± margin, at the same precision as the estimate.

    Every interval here is symmetric — the CIs are the estimate ±2 standard
    errors — so one margin states it exactly. Most are narrow (median ±0.16
    points) and draw smaller than their dot, so this is the only way most
    readers will ever see them.
    """
    # Bounds are stored to two decimals; rounding the half-width to three
    # stops float subtraction turning a true 0.05 into 0.0499… and printing
    # "<0.1" for a margin that rounds to 0.1.
    half = round((row[CI_HIGH] - row[CI_LOW]) / 2, 3)
    return "±<0.1" if half < 0.05 else f"±{half:.1f}"


# =========================================================
# FIGURE BUILDERS
# =========================================================

def empty_figure(message, theme=None):
    p = palette(theme)
    fig = go.Figure()
    fig.add_annotation(
        text=message, showarrow=False,
        font=dict(family=FONT, size=13, color=p["muted"]),
        xref="paper", yref="paper", x=0.5, y=0.5,
    )
    fig.update_layout(
        **base_layout(p),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig


# Width of the value column to the right of each dot-and-interval panel. It
# holds the widest label in the data ("99.9% ±3.8") at 12px with room spare.
VALUE_COLUMN = 92


def wrap_group(label, limit=18):
    """Break an over-long group name at its most central ", " for display.

    Only one name in the data needs it — race's 23-character "A/A Native,
    Asian,Other", against 17 or fewer everywhere else — but it alone set the
    width of the race panel's label column, which on a phone left its plot
    under 80px.
    """
    if len(label) <= limit or ", " not in label:
        return label
    cuts = [i for i in range(len(label)) if label.startswith(", ", i)]
    cut = min(cuts, key=lambda i: abs(i - len(label) / 2))
    return label[:cut + 1] + "<br>" + label[cut + 2:]


def build_dot_interval(rows, height, theme=None):
    """A dot per group with its interval through it and its value in a column.

    The value and margin sit in a right-hand column rather than beside each
    dot: beside the dot they needed the axis padded by half its span on each
    side, which squeezed the intervals they were meant to show. In a column
    they also line up, so the groups read as a ranked table.
    """
    p = palette(theme)
    rows = sorted(rows, key=lambda r: r[PERCENT])
    labels = [r[GROUP] for r in rows]
    values = [r[PERCENT] for r in rows]

    fig = go.Figure()

    # Intervals first, so the dots sit on top. They are drawn heavier than the
    # dot is wide so that any interval wider than its dot visibly overhangs it.
    for row in rows:
        fig.add_trace(go.Scatter(
            x=[row[CI_LOW], row[CI_HIGH]], y=[row[GROUP], row[GROUP]],
            mode="lines", line=dict(color=p["blue"], width=4),
            opacity=p["interval_opacity"], hoverinfo="skip",
        ))

    fig.add_trace(go.Scatter(
        x=values, y=labels, mode="markers",
        marker=dict(size=8, color=p["blue"], line=dict(width=1.5, color=p["surface"])),
        customdata=[(r[CI_LOW], r[CI_HIGH]) for r in rows],
        hovertemplate=(
            "<b>%{y}</b><br>%{x:.2f}%<br>"
            "95% CI %{customdata[0]:.2f} – %{customdata[1]:.2f}<extra></extra>"
        ),
    ))

    value_column = [
        dict(
            # Anchored to the plot's right edge, shifted out into the margin
            # and right-aligned there, so the numbers form a column.
            x=1, xref="paper", xanchor="right", xshift=VALUE_COLUMN - 2,
            y=row[GROUP], yref="y", showarrow=False, align="right",
            text=(f"{row[PERCENT]:.1f}% "
                  f"<span style='color:{p['muted']}'>{margin_text(row)}</span>"),
            font=dict(family=FONT, size=12, color=p["ink"]),
        )
        for row in rows
    ]

    fig.update_layout(
        # Bottom margin leaves room for the tick labels; without it the lowest
        # row sits on top of the axis.
        **{**base_layout(p), "margin": dict(l=8, r=VALUE_COLUMN, t=6, b=26)},
        height=height,
        annotations=value_column,
        xaxis=dict(
            range=axis_window(rows), showgrid=True, gridcolor=p["grid"],
            zeroline=False, ticksuffix="%",
            tickfont=dict(family=FONT, size=11, color=p["muted"]),
        ),
        yaxis=dict(
            showgrid=False, zeroline=False,
            # Display-only wrapping: the rows stay keyed on the real names.
            tickvals=labels, ticktext=[wrap_group(g) for g in labels],
            tickfont=dict(family=FONT, size=12, color=p["ink"]),
        ),
    )
    return fig


def build_sparkline(rows, height, theme=None):
    p = palette(theme)
    rows = sorted(rows, key=lambda r: int(r[GROUP]))
    fig = go.Figure(go.Scatter(
        x=[int(r[GROUP]) for r in rows],
        y=[r[PERCENT] for r in rows],
        mode="lines",
        line=dict(color=p["blue"], width=2.5, shape="spline", smoothing=0.5),
        fill="tozeroy", fillcolor=p["blue_fill"],
        customdata=[(r[CI_LOW], r[CI_HIGH]) for r in rows],
        hovertemplate=(
            "<b>%{x}</b><br>%{y:.2f}%<br>"
            "95% CI %{customdata[0]:.2f} – %{customdata[1]:.2f}<extra></extra>"
        ),
    ))
    values = [r[PERCENT] for r in rows]
    fig.update_layout(
        **{**base_layout(p), "margin": dict(l=8, r=8, t=6, b=22)}, height=height,
        hovermode="x unified",
        xaxis=dict(showgrid=False, zeroline=False, dtick=2,
                   tickfont=dict(family=FONT, size=11, color=p["muted"])),
        yaxis=dict(visible=False, range=[0, max(values) * 1.25]),
    )
    return fig


def build_map(rows, height, theme=None):
    p = palette(theme)
    fig = go.Figure(go.Choropleth(
        locations=[r[GROUP] for r in rows],
        z=[r[PERCENT] for r in rows],
        locationmode="USA-states",
        colorscale=p["sequential"],
        marker_line_color=p["surface"], marker_line_width=1,
        colorbar=dict(thickness=10, len=0.7, outlinewidth=0, ticksuffix="%",
                      tickfont=dict(family=FONT, size=11, color=p["muted"])),
        # Fall back to the code itself if a location is ever unnamed, so the
        # hover degrades to today's behaviour rather than showing nothing.
        customdata=[
            (STATE_NAMES.get(r[GROUP], r[GROUP]), r[CI_LOW], r[CI_HIGH])
            for r in rows
        ],
        hovertemplate=(
            "<b>%{customdata[0]}</b> (%{location})<br>%{z:.2f}%<br>"
            "95% CI %{customdata[1]:.2f} – %{customdata[2]:.2f}<extra></extra>"
        ),
    ))
    fig.update_layout(
        **{**base_layout(p), "margin": dict(l=0, r=0, t=0, b=0)}, height=height,
        # Plotly fits the usa scope at about a third of the available area by
        # default, which leaves the map floating in the card; scale 1 fills it.
        geo=dict(scope="usa", bgcolor=p["surface"], lakecolor=p["surface"],
                 landcolor=p["land"], subunitcolor=p["surface"],
                 projection=dict(scale=1.0)),
    )
    return fig


# =========================================================
# DASH APP
# =========================================================
app = Dash(__name__, title="BRFSS Interactive Dashboard")
server = app.server  # WSGI entry point for Vercel / gunicorn

# Resolve the theme in <head>, before anything paints. Without this, a visitor
# who chose dark would see the light page until Dash booted and ran the
# clientside callback below. The stylesheet keys off this attribute, and since
# a Dash page can't render without JavaScript there is no no-script case to
# cover with a media query.
THEME_BOOT = """<script>
        (function () {
            var choice = "system";
            try { choice = localStorage.getItem("brfss-theme") || "system"; } catch (e) {}
            var dark = choice === "dark" || (choice !== "light" && window.matchMedia &&
                window.matchMedia("(prefers-color-scheme: dark)").matches);
            document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
        })();
        </script>
        """
app.index_string = app.index_string.replace("{%css%}", THEME_BOOT + "{%css%}")


def selector(label, component):
    return html.Div(className="selector", children=[
        html.Label(label, className="selector-label"),
        component,
    ])


def card(children, className="card"):
    return html.Div(className=className, children=children)


app.layout = html.Div(className="page", children=[

    # The resolved theme ("light" or "dark") that the figure callbacks read,
    # and a ping that assets/theme.js sets when the OS setting flips.
    dcc.Store(id="theme-store"),
    dcc.Store(id="os-theme"),

    html.Header(className="header", children=[
        html.Div(className="header-text", children=[
            html.H1("BRFSS Interactive Dashboard", className="title"),
            html.P(
                "CDC Behavioral Risk Factor Surveillance System, 2011–present. "
                "Every estimate is pooled across states and carries a 95% confidence interval.",
                className="subtitle",
            ),
        ]),
        html.Div(className="control-group theme-switch", children=[
            html.Span("Theme", className="control-label"),
            dcc.RadioItems(
                id="theme-rd", className="chips chips-small",
                options=THEME_OPTIONS, value="system", inline=True,
                persistence=True, persistence_type="local",
            ),
        ]),
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

        # The map's graph is mounted by its callback rather than sitting here
        # empty. Plotly fits a geo projection once, at mount, and a graph that
        # mounts inside the hidden results container fits to a zero-size box —
        # it then keeps that scale and renders the map a few pixels wide, since
        # geo (unlike the cartesian panels) does not refit on resize.
        card([
            html.P(id="map-label", className="card-label"),
            html.Div(id="state-graph"),
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
# THEME
# =========================================================
# Runs in the browser: it needs matchMedia and localStorage, and a server round
# trip would only add latency to every toggle. It resolves "system" against the
# OS, keeps the <html> attribute and the stored choice in step, and only
# publishes a new theme when the resolved value actually changes, so an OS flip
# under an explicit choice doesn't redraw every figure for nothing.
app.clientside_callback(
    """
    function (choice, osTheme, current) {
        var prefersDark = window.matchMedia &&
            window.matchMedia("(prefers-color-scheme: dark)").matches;
        var resolved = (choice === "light" || choice === "dark")
            ? choice : (prefersDark ? "dark" : "light");
        document.documentElement.setAttribute("data-theme", resolved);
        try { localStorage.setItem("brfss-theme", choice || "system"); } catch (e) {}
        return resolved === current ? window.dash_clientside.no_update : resolved;
    }
    """,
    Output("theme-store", "data"),
    Input("theme-rd", "value"),
    Input("os-theme", "data"),
    State("theme-store", "data"),
)


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
# The theme defaults to None (light) only so tests can call these directly;
# Dash always passes it.

def register_breakdown(panel, label):
    @app.callback(
        Output(f"{panel}-plot", "figure"),
        Input("question-dd", "value"),
        Input("response-rd", "value"),
        Input("mode-rd", "value"),
        Input("theme-store", "data"),
    )
    def update_breakdown(question_id, response, mode, theme=None,
                         panel=panel, label=label):
        rows = apply_filter(panel_rows(question_id, panel, response), mode)
        if not rows:
            return empty_figure(f"No {label.lower()} breakdown for this question", theme)
        # Roughly one row of height per group, so a two-group panel is not
        # stretched to the height of a six-group one. The floor keeps the two
        # -row panels tall enough that the value labels clear the axis.
        return build_dot_interval(rows, height=max(158, 34 * len(rows) + 62),
                                  theme=theme)

    return update_breakdown


for _panel, _label in BREAKDOWNS:
    register_breakdown(_panel, _label)


@app.callback(
    Output("temporal-plot", "figure"),
    Input("question-dd", "value"),
    Input("response-rd", "value"),
    Input("theme-store", "data"),
)
def update_temporal(question_id, response, theme=None):
    rows = panel_rows(question_id, "temporal", response)
    if not rows:
        return empty_figure("No year-by-year data for this question", theme)
    return build_sparkline(rows, height=150, theme=theme)


def state_figure(question_id, response, theme=None):
    """The map figure and its card label, split out so tests can read it."""
    rows = panel_rows(question_id, "state", response)
    if not rows:
        return empty_figure("No state-level data for this question", theme), "By state"
    # Only the selected response is mapped, so every state is shaded on the
    # same quantity — unlike a "highest response per state" rule, which can
    # silently colour different states by different responses.
    return build_map(rows, height=420, theme=theme), f"By state · {len(rows)} reporting"


@app.callback(
    Output("state-graph", "children"),
    Output("map-label", "children"),
    Input("question-dd", "value"),
    Input("response-rd", "value"),
    Input("theme-store", "data"),
)
def update_state(question_id, response, theme):
    figure, label = state_figure(question_id, response, theme)
    return dcc.Graph(id="state-plot", figure=figure, config=GRAPH_CONFIG), label


if __name__ == "__main__":
    app.run(debug=True)
