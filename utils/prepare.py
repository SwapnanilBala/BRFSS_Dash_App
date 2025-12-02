import pandas as pd
from utils.merges import apply_all_merges


def load_question(df: pd.DataFrame, question_text: str) -> pd.DataFrame:
    """
    Extract and clean all rows for a selected question.
    """

    # Step 1 — slice to the question
    qdf = df[df["Question"] == question_text].copy()

    # Fix numeric columns
    qdf["Sample_Size"] = pd.to_numeric(qdf["Sample_Size"], errors="coerce")
    qdf["Data_value"] = pd.to_numeric(qdf["Data_value"], errors="coerce")

    # Apply all merges
    qdf = apply_all_merges(qdf)

    # Remove national rollups
    if "Locationabbr" in qdf.columns:
        qdf = qdf[~qdf["Locationabbr"].isin(["US", "UW"])]

    return qdf
