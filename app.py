import pandas as pd
from dash import Dash, dcc, html, Input, Output
import plotly.express as px
import plotly.graph_objects as go

# utils
from utils.prepare import load_question
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
# LOAD BRFSS CSV + REMOVE CALCULATED VARIABLES
# =========================================================
df = pd.read_csv(
    "/Users/swapnanilbala/Documents/Behavioral_Risk_Factor_Surveillance_System_(BRFSS)_Prevalence_Data_(2011_to_present)_20251129.csv",
    low_memory=False
)

# Remove calculated variables (they do NOT appear in prevalence dataset)
df = df[~df["Question"].str.contains("variable calculated", case=False, na=False)]

print("Unique Questions After Filtering:", len(df["Question"].unique()))
print(df["Question"].unique()[:20])

# =========================================================
# UTILITY FUNCTIONS (REPLACE get_class_options/etc)
# These ensure dropdown uses EXACT text from CSV
# =========================================================

def get_class_options(df):
    return sorted(df["Class"].dropna().unique().tolist())

def get_topic_options(df, selected_class):
    if not selected_class:
        return []
    topics = df[df["Class"] == selected_class]["Topic"].dropna().unique().tolist()
    return sorted(topics)

def get_question_options(df, selected_class, selected_topic):
    if not selected_class or not selected_topic:
        return []
    qs = df[
        (df["Class"] == selected_class) &
        (df["Topic"] == selected_topic)
    ]["Question"].dropna().unique().tolist()
    return sorted(qs)

class_options = get_class_options(df)

# =========================================================
# DASH APP
# =========================================================
app = Dash(__name__)

# =========================================================
# Helper: FILTER "more/less/all"
# =========================================================
def apply_filter(summary, mode):
    if summary.empty:
        return summary
    if mode == "more":
        return summary.sort_values("percent", ascending=False).head(3)
    if mode == "less":
        return summary.sort_values("percent", ascending=True).head(3)
    return summary


# =========================================================
# Helper: ERROR BAR BAR CHART BUILDER
# =========================================================
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


# =========================================================
# LAYOUT
# =========================================================
app.layout = html.Div(style={'padding': '20px'}, children=[

    html.H2("BRFSS Interactive Dashboard"),
    html.H3("Select a Question"),

    # CLASS -> TOPIC -> QUESTION
    dcc.Dropdown(
        id="class-dd",
        options=[{"label": c, "value": c} for c in class_options],
        placeholder="Select Class",
        style={'width': '60%'}
    ),

    dcc.Dropdown(
        id="topic-dd",
        placeholder="Select Topic",
        style={'width': '60%', 'marginTop': '10px'}
    ),

    dcc.Dropdown(
        id="question-dd",
        placeholder="Select Question",
        style={'width': '60%', 'marginTop': '10px'}
    ),

    html.Div(id="selected-question-display",
             style={'marginTop': '15px', 'fontSize': '18px',
                    'color': 'darkblue'}),

    html.Hr(),

    # =========================================================
    # TABS
    # =========================================================
    dcc.Tabs([

        dcc.Tab(label="Overall", children=[
            html.Br(),
            dcc.Dropdown(
                id="overall-filter",
                options=[
                    {"label":"Show All","value":"all"},
                    {"label":"More (Top 3)","value":"more"},
                    {"label":"Less (Bottom 3)","value":"less"}
                ],
                value="all",
                style={'width':'30%'}
            ),
            dcc.Loading(children=dcc.Graph(id="overall-plot"))
        ]),

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
                style={'width':'30%'}
            ),
            dcc.Loading(children=dcc.Graph(id="gender-plot"))
        ]),

        dcc.Tab(label="Age Group", children=[
            html.Br(),
            dcc.Dropdown(
                id="age-filter",
                options=[
                    {"label": "Show All", "value": "all"},
                    {"label": "More (Top 3)", "value": "more"},
                    {"label": "Less (Bottom 3)", "value": "less"}
                ],
                value="all",
                style={'width':'30%'}
            ),
            dcc.Loading(children=dcc.Graph(id="age-plot"))
        ]),

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
                style={'width':'30%'}
            ),
            dcc.Loading(children=dcc.Graph(id="race-plot"))
        ]),

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
                style={'width':'30%'}
            ),
            dcc.Loading(children=dcc.Graph(id="education-plot"))
        ]),

        dcc.Tab(label="Income", children=[
            html.Br(),
            dcc.Dropdown(
                id="income-filter",
                options=[
                    {"label":"Show All","value":"all"},
                    {"label":"More (Top 3)","value":"more"},
                    {"label":"Less (Bottom 3)","value":"less"}
                ],
                value="all",
                style={'width':'30%'}
            ),
            dcc.Loading(children=dcc.Graph(id="income-plot"))
        ]),

        dcc.Tab(label="Temporal", children=[
            html.Br(),
            dcc.Dropdown(
                id="temporal-filter",
                options=[
                    {"label":"Show All","value":"all"},
                    {"label":"More (Top 3)","value":"more"},
                    {"label":"Less (Bottom 3)","value":"less"}
                ],
                value="all",
                style={'width':'30%'}
            ),
            dcc.Loading(children=dcc.Graph(id="temporal-plot"))
        ]),

        dcc.Tab(label="State/Territory", children=[
            html.Br(),
            dcc.Dropdown(
                id="state-filter",
                options=[
                    {"label":"Show All","value":"all"},
                    {"label":"More (Top 3)","value":"more"},
                    {"label":"Less (Bottom 3)","value":"less"}
                ],
                value="all",
                style={'width':'30%'}
            ),
            dcc.Loading(children=dcc.Graph(id="state-plot"))
        ])
    ])
])


# =========================================================
# CALLBACKS TO POPULATE TOPIC + QUESTION DROPDOWNS
# =========================================================

@app.callback(
    Output("topic-dd", "options"),
    Input("class-dd", "value")
)
def update_topics(selected_class):
    topics = get_topic_options(df, selected_class)
    return [{"label": t, "value": t} for t in topics]


@app.callback(
    Output("question-dd", "options"),
    Input("class-dd", "value"),
    Input("topic-dd", "value")
)
def update_questions(selected_class, selected_topic):
    qs = get_question_options(df, selected_class, selected_topic)
    return [{"label": q, "value": q} for q in qs]


@app.callback(
    Output("selected-question-display", "children"),
    Input("question-dd", "value")
)
def show_selected(q):
    return f"Selected Question: {q}" if q else ""


# =========================================================
# PANEL CALLBACKS
# =========================================================

def safe_empty_figure(title="No data"):
    return go.Figure(layout={"title": title})


# OVERALL PANEL
@app.callback(
    Output("overall-plot", "figure"),
    Input("question-dd", "value"),
    Input("overall-filter", "value")
)
def update_overall(q, mode):
    if not q:
        return go.Figure()
    summary = aggregate_overall(load_question(df, q))
    summary = apply_filter(summary, mode)
    if summary.empty:
        return safe_empty_figure()
    return build_ci_bar(summary, "Response", "Overall Summary")


# GENDER PANEL
@app.callback(
    Output("gender-plot", "figure"),
    Input("question-dd", "value"),
    Input("gender-filter", "value")
)
def update_gender(q, mode):
    if not q:
        return go.Figure()
    summary = aggregate_gender(load_question(df, q))
    summary = apply_filter(summary, mode)
    if summary.empty:
        return safe_empty_figure()
    return build_ci_bar(summary, "Break_Out", "By Gender")


# AGE PANEL
@app.callback(
    Output("age-plot", "figure"),
    Input("question-dd", "value"),
    Input("age-filter", "value")
)
def update_age(q, mode):
    if not q:
        return go.Figure()
    summary = aggregate_age(load_question(df, q))
    summary = apply_filter(summary, mode)
    if summary.empty:
        return safe_empty_figure()
    return build_ci_bar(summary, "Break_Out", "By Age Group")


# RACE PANEL
@app.callback(
    Output("race-plot", "figure"),
    Input("question-dd", "value"),
    Input("race-filter", "value")
)
def update_race(q, mode):
    if not q:
        return go.Figure()
    summary = aggregate_race(load_question(df, q))
    summary = apply_filter(summary, mode)
    if summary.empty:
        return safe_empty_figure()
    return build_ci_bar(summary, "Break_Out", "By Race")


# EDUCATION PANEL
@app.callback(
    Output("education-plot", "figure"),
    Input("question-dd", "value"),
    Input("education-filter", "value")
)
def update_education(q, mode):
    if not q:
        return go.Figure()
    summary = aggregate_education(load_question(df, q))
    summary = apply_filter(summary, mode)
    if summary.empty:
        return safe_empty_figure()
    return build_ci_bar(summary, "Break_Out", "By Education")


# INCOME PANEL
@app.callback(
    Output("income-plot", "figure"),
    Input("question-dd", "value"),
    Input("income-filter", "value")
)
def update_income(q, mode):
    if not q:
        return go.Figure()
    summary = aggregate_income(load_question(df, q))
    summary = apply_filter(summary, mode)
    if summary.empty:
        return safe_empty_figure()
    return build_ci_bar(summary, "Break_Out", "By Income")


# TEMPORAL PANEL
@app.callback(
    Output("temporal-plot", "figure"),
    Input("question-dd", "value"),
    Input("temporal-filter", "value")
)
def update_temporal(q, mode):
    if not q:
        return go.Figure()
    summary = aggregate_temporal(load_question(df, q))
    summary = apply_filter(summary, mode)
    if summary.empty or "Year" not in summary.columns:
        return safe_empty_figure("No temporal data")

    summary = summary.sort_values("Year")

    fig = px.line(
        summary,
        x="Year",
        y="percent",
        color="Response",
        markers=True,
        title="Temporal Trend"
    )

    return fig


# STATE PANEL
@app.callback(
    Output("state-plot", "figure"),
    Input("question-dd", "value"),
    Input("state-filter", "value")
)
def update_state(q, mode):
    if not q:
        return go.Figure()
    summary = aggregate_state(load_question(df, q))
    summary = apply_filter(summary, mode)
    if summary.empty:
        return safe_empty_figure("No state data")

    summary = summary.sort_values("Locationabbr")
    return build_ci_bar(summary, "Locationabbr", "By State")


# Debug test:
qdf = load_question(df, "Ever told you that you have a form of depression?")
print("\n=== DEBUG LOAD_QUESTION OUTPUT ===")
print(qdf.head())
print("========================\n")


# RUN APP
if __name__ == "__main__":
    app.run(debug=True)
