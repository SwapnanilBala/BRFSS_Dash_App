import pandas as pd
from utils.merges import apply_all_merges

def load_question(df: pd.DataFrame, question_text: str) -> pd.DataFrame:
    qdf = df[df["Question"] == question_text].copy()

    # Fix numeric
    qdf["Sample_Size"] = pd.to_numeric(qdf["Sample_Size"], errors="coerce")
    qdf["Data_value"] = pd.to_numeric(qdf["Data_value"], errors="coerce")

    # Apply merges
    qdf = apply_all_merges(qdf)

    # Remove national rows (US)
    if "Locationabbr" in qdf:
        qdf = qdf[~qdf["Locationabbr"].isin(["US", "UW"])]

    return qdf
