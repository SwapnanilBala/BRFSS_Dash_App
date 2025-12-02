# utils/aggregation.py

import pandas as pd
import numpy as np
from utils.merges import (
    merge_response_id,
    merge_response_text,
    merge_breakout_id,
    merge_break_out
)


def compute_panel(qdf, cat_id, group_cols):
    if qdf.empty:
        return pd.DataFrame()

    # Filter breakout category
    df = qdf[qdf["BreakOutCategoryID"] == cat_id].copy()
    if df.empty:
        return pd.DataFrame()

    # Normalize data value column
    if "Data_Value" in df.columns:
        value_col = "Data_Value"
    elif "Data_value" in df.columns:
        value_col = "Data_value"
    else:
        print("[compute_panel] No Data Value column found")
        print(df.columns.tolist())
        return pd.DataFrame()

    # Convert to numeric
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")

    # Remove national rows
    df = df[~df["Locationabbr"].isin(["US", "UW"])]

    # Remove invalid rows
    df = df.dropna(subset=["Sample_Size", value_col])
    if df.empty:
        return pd.DataFrame()

    # Weight calculations
    df["persons"] = df["Sample_Size"]
    df["true_ss"] = df["persons"] * 100 / df[value_col]

    # Grouping
    group = df.groupby(group_cols + ["Response"]).agg(
        persons_sum=("persons", "sum"),
        ss_sum=("true_ss", "sum")
    ).reset_index()

    # Percent + CI
    group["percent"] = group["persons_sum"] * 100 / group["ss_sum"]
    group["sdev"] = np.sqrt(group["percent"] * (100 - group["percent"]) / group["ss_sum"])
    group["ci_low"] = group["percent"] - 2 * group["sdev"]
    group["ci_high"] = group["percent"] + 2 * group["sdev"]

    return group


# PANEL FUNCTIONS
def aggregate_overall(qdf):
    return compute_panel(qdf, "CAT1", [])


def aggregate_gender(qdf):
    return compute_panel(qdf, "CAT2", ["Break_Out"])


def aggregate_age(qdf):
    return compute_panel(qdf, "CAT3", ["Break_Out"])


def aggregate_race(qdf):
    return compute_panel(qdf, "CAT4", ["Break_Out"])


def aggregate_education(qdf):
    return compute_panel(qdf, "CAT5", ["Break_Out"])


def aggregate_income(qdf):
    return compute_panel(qdf, "CAT6", ["Break_Out"])


def aggregate_temporal(qdf):
    return compute_panel(qdf, "CAT1", ["Year"])


def aggregate_state(qdf):
    return compute_panel(qdf, "CAT1", ["Locationabbr"])
