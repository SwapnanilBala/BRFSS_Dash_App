import pandas as pd

# ---------------------------------------------------------
# DROPDOWN OPTIONS HELPERS
# ---------------------------------------------------------

def get_class_options(df):
    """Return sorted unique Class values."""
    return sorted(df["Class"].dropna().unique())


def get_topic_options(df, selected_class):
    """Return all unique topics for a given class."""
    if not selected_class:
        return []
    mask = df["Class"] == selected_class
    topics = df.loc[mask, "Topic"].dropna().unique()
    return sorted(topics)


def get_question_options(df, selected_class, selected_topic):
    """Return all unique questions for a selected (Class, Topic)."""
    if not selected_class or not selected_topic:
        return []
    mask = (df["Class"] == selected_class) & (df["Topic"] == selected_topic)
    questions = df.loc[mask, "Question"].dropna().unique()
    return sorted(questions)
