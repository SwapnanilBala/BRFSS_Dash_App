import pandas as pd
from dash import Dash, dcc, html, Input, Output
import plotly.express as px
import plotly.graph_objects as go

# utils
from utils.prepare import load_question
from utils.options import get_class_options, get_topic_options, get_question_options
from utils.aggregation import (
    aggregate_overall,
    aggregate_gender,
    aggregate_age,
    aggregate_race,
    aggregate_education,
    aggregate_income,
    aggregate_temporal,
    aggregate_state
)

# =========================================================
# LOAD CSV (NO FILTERS!)
# =========================================================
df = pd.read_csv(
    "/Users/swapnanilbala/Documents/Behavioral_Risk_Factor_Surveillance_System_(BRFSS)_Prevalence_Data_(2011_to_present)_20251129.csv",
    low_memory=False
)

class_options = get_class_options(df)

# =========================================================
# HELPERS
# =========================================================

def apply_filter(summary, mode):
    if summary.empty:
        return summary
    if mode == "more":
        return summary.sort_values("percent", ascending=False).head(3)
    if mode == "less":
        return summary.sort_values("percent", ascending=True).head(3)
    return summary


def build_ci_bar(summary, x_col, title):
    fig = px.bar(
        summary,
        x=x_col,
        y="percent",
        color="Response",
        barmode="group",
        title=title,
        hover_data={"percent":":.2f","ci_low":":.2f","ci_high":":.2f"}
    )

    fig.update_traces(
        error_y=dict(
            symmetric=False,
            array=summary["ci_high"] - summary["percent"],
            arrayminus=summary["percent"] - summary["ci_low"]
        )
    )
    fig.update_layout(yaxis_title="Percent (%)")
    return fig


def build_geo_map(summary):
    """Option B — pick the HIGHEST RESPONSE per state."""
    if summary.empty:
        return go.Figure(layout={"title": "No state-level data available"})

    best = summary.sort_values("percent", ascending=False).groupby("Locationabbr").head(1)
    best = best[best["Locationabbr"].str.len() == 2]  # keep only valid states

    fig = px.choropleth(
        best,
        locations="Locationabbr",
        locationmode="USA-states",
        color="percent",
        scope="usa",
        color_continuous_scale="Plasma",
        hover_name="Locationabbr",
        title="State-Level Prevalence (Highest Response per State)"
    )
    fig.update_layout(margin={"l":0,"r":0,"t":50,"b":0})
    return fig


# =========================================================
# DASH APP
# =========================================================
app = Dash(__name__)

app.layout = html.Div(style={'padding': '20px'}, children=[

    html.H1("BRFSS Interactive Dashboard"),

    # -------------------- TOP DROPDOWNS --------------------
    html.Div(style={'display': 'flex', 'gap': '15px'}, children=[
        dcc.Dropdown(
            id="class-dd",
            options=[{"label": c, "value": c} for c in class_options],
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

        # ==================== OVERALL ====================
        dcc.Tab(label="Overall", children=[
            html.Br(),
            dcc.Dropdown(
                id="overall-filter",
                options=[
                    {"label": "Show All", "value": "all"},
                    {"label": "More (Top 3)", "value": "more"},
                    {"label": "Less (Bottom 3)", "value": "less"}
                ],
                value="all",
                style={'width': '25%'}
            ),
            dcc.Graph(id="overall-plot")
        ]),

        # ==================== GENDER ====================
        dcc.Tab(label="Gender", children=[
            html.Br(),
            dcc.Dropdown(
                id="gender-filter",
                options=[
                    {"label": "Show All", "value": "all"},
                    {"label": "More (Top 3)", "value": "more"},
                    {"label": "Less (Bottom 3)", "value": "less"}
                ],
                value="all",
                style={'width': '25%'}
            ),
            dcc.Graph(id="gender-plot")
        ]),

        # ==================== AGE ====================
        dcc.Tab(label="Age", children=[
            html.Br(),
            dcc.Dropdown(
                id="age-filter",
                options=[
                    {"label": "Show All", "value": "all"},
                    {"label": "More (Top 3)", "value": "more"},
                    {"label": "Less (Bottom 3)", "value": "less"}
                ],
                value="all",
                style={'width': '25%'}
            ),
            dcc.Graph(id="age-plot")
        ]),

        # ==================== RACE ====================
        dcc.Tab(label="Race", children=[
            html.Br(),
            dcc.Dropdown(
                id="race-filter",
                options=[
                    {"label": "Show All", "value": "all"},
                    {"label": "More (Top 3)", "value": "more"},
                    {"label": "Less (Bottom 3)", "value": "less"}
                ],
                value="all",
                style={'width': '25%'}
            ),
            dcc.Graph(id="race-plot")
        ]),

        # ==================== EDUCATION ====================
        dcc.Tab(label="Education", children=[
            html.Br(),
            dcc.Dropdown(
                id="education-filter",
                options=[
                    {"label": "Show All", "value": "all"},
                    {"label": "More (Top 3)", "value": "more"},
                    {"label": "Less (Bottom 3)", "value": "less"}
                ],
                value="all",
                style={'width': '25%'}
            ),
            dcc.Graph(id="education-plot")
        ]),

        # ==================== INCOME ====================
        dcc.Tab(label="Income", children=[
            html.Br(),
            dcc.Dropdown(
                id="income-filter",
                options=[
                    {"label": "Show All", "value": "all"},
                    {"label": "More (Top 3)", "value": "more"},
                    {"label": "Less (Bottom 3)", "value": "less"}
                ],
                value="all",
                style={'width': '25%'}
            ),
            dcc.Graph(id="income-plot")
        ]),

        # ==================== TEMPORAL ====================
        dcc.Tab(label="Temporal", children=[
            html.Br(),
            dcc.Dropdown(
                id="temporal-filter",
                options=[
                    {"label": "Show All", "value": "all"},
                    {"label": "More (Top 3)", "value": "more"},
                    {"label": "Less (Bottom 3)", "value": "less"}
                ],
                value="all",
                style={'width': '25%'}
            ),
            dcc.Graph(id="temporal-plot")
        ]),

        # ==================== STATE MAP ====================
        dcc.Tab(label="State / Territory Heatmap", children=[
            html.Br(),
            dcc.Dropdown(
                id="state-filter",
                options=[
                    {"label": "Show All", "value": "all"},
                    {"label": "More (Top 3)", "value": "more"},
                    {"label": "Less (Bottom 3)", "value": "less"}
                ],
                value="all",
                style={'width': '25%'}
            ),
            dcc.Graph(id="state-map")
        ])
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
    topics = get_topic_options(df, c)
    return [{"label": t, "value": t} for t in topics]


@app.callback(
    Output("question-dd", "options"),
    Input("class-dd", "value"),
    Input("topic-dd", "value")
)
def update_questions(c, t):
    qs = get_question_options(df, c, t)
    return [{"label": q, "value": q} for q in qs]


@app.callback(
    Output("selected-question-display", "children"),
    Input("question-dd", "value")
)
def show_q(q):
    if not q:
        return "📌 No question selected"
    return f"📌 Selected Question: {q}"


# =========================================================
# PANEL CALLBACKS
# =========================================================

@app.callback(
    Output("overall-plot", "figure"),
    Input("question-dd", "value"),
    Input("overall-filter", "value")
)
def update_overall(q, mode):
    if not q:
        return go.Figure()
    summary = apply_filter(aggregate_overall(load_question(df, q)), mode)
    if summary.empty:
        return go.Figure(layout={"title":"No aggregation possible"})
    return build_ci_bar(summary, "Response", "Overall Summary")


@app.callback(
    Output("gender-plot", "figure"),
    Input("question-dd", "value"),
    Input("gender-filter", "value")
)
def update_gender(q, mode):
    if not q:
        return go.Figure()
    summary = apply_filter(aggregate_gender(load_question(df, q)), mode)
    if summary.empty:
        return go.Figure(layout={"title":"No gender data"})
    return px.bar(summary, y="Break_Out", x="percent", color="Response",
                  orientation="h", title="By Gender")


@app.callback(
    Output("age-plot", "figure"),
    Input("question-dd", "value"),
    Input("age-filter", "value")
)
def update_age(q, mode):
    if not q:
        return go.Figure()
    summary = apply_filter(aggregate_age(load_question(df, q)), mode)
    if summary.empty:
        return go.Figure(layout={"title":"No age data"})
    return build_ci_bar(summary, "Break_Out", "By Age Group")


@app.callback(
    Output("race-plot", "figure"),
    Input("question-dd", "value"),
    Input("race-filter", "value")
)
def update_race(q, mode):
    if not q:
        return go.Figure()
    summary = apply_filter(aggregate_race(load_question(df, q)), mode)
    if summary.empty:
        return go.Figure(layout={"title":"No race data"})
    return build_ci_bar(summary, "Break_Out", "By Race")


@app.callback(
    Output("education-plot", "figure"),
    Input("question-dd", "value"),
    Input("education-filter", "value")
)
def update_education(q, mode):
    if not q:
        return go.Figure()
    summary = apply_filter(aggregate_education(load_question(df, q)), mode)
    if summary.empty:
        return go.Figure(layout={"title":"No education data"})
    return build_ci_bar(summary, "Break_Out", "By Education")


@app.callback(
    Output("income-plot", "figure"),
    Input("question-dd", "value"),
    Input("income-filter", "value")
)
def update_income(q, mode):
    if not q:
        return go.Figure()
    summary = apply_filter(aggregate_income(load_question(df, q)), mode)
    if summary.empty:
        return go.Figure(layout={"title":"No income data"})
    return build_ci_bar(summary, "Break_Out", "By Income")


@app.callback(
    Output("temporal-plot", "figure"),
    Input("question-dd", "value"),
    Input("temporal-filter", "value")
)
def update_temporal(q, mode):
    if not q:
        return go.Figure()
    summary = apply_filter(aggregate_temporal(load_question(df, q)), mode)
    if summary.empty:
        return go.Figure(layout={"title":"No temporal data"})
    summary = summary.sort_values("Year")
    return px.line(summary, x="Year", y="percent", color="Response", markers=True,
                   title="Temporal Trend")


@app.callback(
    Output("state-map", "figure"),
    Input("question-dd", "value"),
    Input("state-filter", "value")
)
def update_state(q, mode):
    if not q:
        return go.Figure()
    summary = apply_filter(aggregate_state(load_question(df, q)), mode)
    if summary.empty:
        return go.Figure(layout={"title":"No state data"})
    return build_geo_map(summary)


if __name__ == "__main__":
    app.run(debug=True)
