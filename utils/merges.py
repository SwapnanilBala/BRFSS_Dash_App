# utils/merges.py

import pandas as pd
import numpy as np


# ---------- ResponseID merge (R: merge_ResponseID) ----------

def merge_response_id(series: pd.Series) -> pd.Series:
    """
    Merge older / alternative ResponseID codes into unified ones.
    Mirrors the R merge_ResponseID() function.
    """
    s = series.astype("string").copy()

    replacements = {
        "RESP025": "RESP137",
        "RESP026": "RESP172",
        "RESP029": "RESP141",
        "RESP230": "RESP020",
        "RESP231": "RESP020",
        "RESP232": "RESP020",
        "RESP196": "RESP199",
        "RESP197": "RESP199",
        "RESP198": "RESP199",
        "RESP199": "RESP199",
        "RESP200": "RESP008",
        "RESP194": "RESP005",
        "RESP195": "RESP006",
    }

    for old, new in replacements.items():
        s = s.str.replace(old, new, regex=False)

    return s


# ---------- Response text merge (R: merge_Response) ----------

def merge_response_text(response_id: pd.Series,
                        response: pd.Series) -> pd.Series:
    """
    Standardize the Response labels based on merged ResponseID.
    Mirrors the R merge_Response() function.
    """
    resp_id = response_id.astype("string")
    resp = response.astype("string").copy()

    # Same logic as in R
    idx = resp_id.str.contains("RESP137", na=False)
    resp.loc[idx] = "Employed"

    idx = resp_id.str.contains("RESP172", na=False)
    resp.loc[idx] = "Self-employed"

    idx = resp_id.str.contains("RESP141", na=False)
    resp.loc[idx] = "Homemaker"

    idx = resp_id.str.contains("RESP020", na=False)
    resp.loc[idx] = "$50,000+"

    idx = resp_id.str.contains("RESP199", na=False)
    resp.loc[idx] = "A/A Native, Asian,Other"

    idx = resp_id.str.contains("RESP008", na=False)
    resp.loc[idx] = "Multiracial"

    idx = resp_id.str.contains("RESP005", na=False)
    resp.loc[idx] = "White"

    idx = resp_id.str.contains("RESP006", na=False)
    resp.loc[idx] = "Black"

    # Make all responses lower case (as in R)
    resp = resp.str.lower()

    return resp


# ---------- BreakoutID merge (R: merge_BreakoutID) ----------

def merge_breakout_id(series: pd.Series) -> pd.Series:
    """
    Merge BreakoutID values where categories were refined over time.
    Mirrors the R merge_BreakoutID() function.
    """
    s = series.astype("string").copy()

    replacements = {
        "INCOME01": "INCOME1",
        "INCOME02": "INCOME2",
        "INCOME03": "INCOME3",
        "INCOME04": "INCOME4",
        "INCOME05": "INCOME5",
        "INCOME06": "INCOME5",
        "INCOME07": "INCOME5",
        "RACE01": "RACE1",
        "RACE02": "RACE2",
        "RACE08": "RACE3",
        "RACE04": "RACE4",
        "RACE05": "RACE4",
        "RACE06": "RACE4",
        "RACE03": "RACE4",
        "RACE07": "RACE5",
    }

    for old, new in replacements.items():
        s = s.str.replace(old, new, regex=False)

    return s


# ---------- Break_Out label merge (R: merge_Break_Out) ----------

def merge_break_out(breakout_id: pd.Series,
                    break_out: pd.Series) -> pd.Series:
    """
    Standardize Break_Out labels based on merged BreakoutID.
    Mirrors the R merge_Break_Out() function.
    """
    bid = breakout_id.astype("string")
    bo = break_out.astype("string").copy()

    idx = bid.str.contains("INCOME5", na=False)
    bo.loc[idx] = "$50,000+"

    idx = bid.str.contains("RACE1", na=False)
    bo.loc[idx] = "White"

    idx = bid.str.contains("RACE2", na=False)
    bo.loc[idx] = "Black"

    idx = bid.str.contains("RACE3", na=False)
    bo.loc[idx] = "Hispanic"

    idx = bid.str.contains("RACE4", na=False)
    bo.loc[idx] = "A/A Native, Asian,Other"

    idx = bid.str.contains("RACE5", na=False)
    bo.loc[idx] = "Multiracial"

    return bo


# ---------- High-level helper: clean a question-level dataframe ----------

def apply_all_merges(qdf: pd.DataFrame) -> pd.DataFrame:
    """
    Safely apply response + breakout merges without altering panel structure.
    """
    df = qdf.copy()

    # --- RESPONSE ID FIX (row-wise)
    df["ResponseID"] = merge_response_id(df["ResponseID"])

    # --- RESPONSE TEXT FIX (row-wise)
    df["Response"] = merge_response_text(df["ResponseID"], df["Response"])

    # --- BREAKOUT ID FIX (row-wise)
    df["BreakoutID"] = merge_breakout_id(df["BreakoutID"])

    # --- BREAK OUT LABEL FIX (row-wise)
    df["Break_Out"] = merge_break_out(df["BreakoutID"], df["Break_Out"])

    # --- CRITICAL ---
    # KEEP BreakOutCategoryID AS-IS
    # Do NOT rewrite it based on BreakoutID
    # This is what drives CAT1...CAT6 panels.
    # If we alter this, ALL panels break.

    return df

