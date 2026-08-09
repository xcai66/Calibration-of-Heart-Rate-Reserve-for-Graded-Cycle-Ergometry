#!/usr/bin/env python3
"""Extract and quality-control the Zenodo graded exercise test workbooks.

The script treats a complete graded test as the analysis unit. Stage-level
records are retained only after test-level physiological anchors can be formed.
No model selection is performed here.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re

import numpy as np
import pandas as pd


SPORT_LABELS = {
    "cycling": "Cycling",
    "running": "Running",
    "rowing": "Rowing",
    "kayak": "Kayak",
    "kayaking": "Kayak",
}


def numeric(value):
    """Coerce spreadsheet cells to numbers while preserving missing values."""
    if pd.isna(value):
        return np.nan
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
        value = re.sub(r"[^0-9eE+\-.]", "", value)
        if not value:
            return np.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def key_value_sheet(path: Path, sheet: str) -> dict[str, object]:
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    result: dict[str, object] = {}
    for _, row in raw.iterrows():
        if len(row) < 2 or pd.isna(row.iloc[0]):
            continue
        result[str(row.iloc[0]).strip().rstrip(":")] = row.iloc[1]
    return result


def canonical_sport(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip().lower()
    for key, label in SPORT_LABELS.items():
        if key in text:
            return label
    return str(value).strip().title()


def parse_date(value: object):
    if isinstance(value, str):
        return pd.to_datetime(value, errors="coerce", dayfirst=True)
    return pd.to_datetime(value, errors="coerce")


def finite_max(*values):
    values = [numeric(v) for v in values]
    values = [v for v in values if np.isfinite(v)]
    return max(values) if values else np.nan


def extract_one(path: Path, summary_row: pd.Series | None):
    meta = key_value_sheet(path, "Sheet1")
    endpoints = key_value_sheet(path, "Sheet3")
    stages = pd.read_excel(path, sheet_name="Sheet2")
    stages.columns = [str(c).strip() for c in stages.columns]

    column_map = {}
    for column in stages.columns:
        low = column.lower()
        if ("actual" in low and ("power" in low or "load" in low)) or low in {"velocity", "speed", "power", "load"}:
            column_map[column] = "load"
        elif low == "hr" or "heart rate" in low:
            column_map[column] = "hr"
        elif "vo2" in low or "oxygen" in low:
            column_map[column] = "vo2"
        elif low == "bla" or "lactate" in low:
            column_map[column] = "lactate"
        elif "cadence" in low or low in {"sr", "stroke rate"}:
            column_map[column] = "cadence"
    stages = stages.rename(columns=column_map)
    required = {"load", "hr", "vo2"}
    if not required.issubset(stages.columns):
        return None, {"file": path.name, "status": "excluded", "reason": "missing_required_columns"}

    for column in ["load", "hr", "vo2", "lactate", "cadence"]:
        if column not in stages:
            stages[column] = np.nan
        stages[column] = stages[column].map(numeric)
    stages = stages.dropna(subset=["load", "hr", "vo2"]).reset_index(drop=True)

    fallback = summary_row if summary_row is not None else pd.Series(dtype=object)
    sport = canonical_sport(meta.get("Test", meta.get("Event", fallback.get("sport"))))
    gender = meta.get("Gender", fallback.get("gender"))
    test_date = parse_date(meta.get("Test Date", fallback.get("test_date")))
    dob = parse_date(meta.get("DOB", fallback.get("DOB")))
    age = (test_date - dob).days / 365.2425 if pd.notna(test_date) and pd.notna(dob) else np.nan

    # Stage 0 is the recorded unloaded/rest stage. If no exact zero is present,
    # the lowest-load stage is used and explicitly flagged.
    min_load = stages["load"].min()
    baseline_rows = stages.loc[stages["load"] == min_load]
    hr0 = float(baseline_rows["hr"].median())
    vo20 = float(baseline_rows["vo2"].median())
    hrmax_reported = numeric(endpoints.get("Hrmax", fallback.get("HRmax")))
    vo2max_reported = numeric(endpoints.get("VO2max", fallback.get("vo2max")))
    hrmax = finite_max(hrmax_reported, stages["hr"].max())
    vo2max = finite_max(vo2max_reported, stages["vo2"].max())
    max_load = float(stages["load"].max())

    active = stages.loc[stages["load"] > min_load].copy()
    reasons = []
    if sport not in {"Cycling", "Running", "Rowing", "Kayak"}:
        reasons.append("unsupported_sport")
    if len(active) < 4:
        reasons.append("fewer_than_4_active_stages")
    if not (np.isfinite(hr0) and np.isfinite(hrmax) and hrmax - hr0 >= 40):
        reasons.append("invalid_hr_anchor")
    if not (np.isfinite(vo20) and np.isfinite(vo2max) and vo2max - vo20 >= 10):
        reasons.append("invalid_vo2_anchor")
    if not (np.isfinite(max_load) and max_load - min_load > 0):
        reasons.append("invalid_load_anchor")
    if reasons:
        return None, {"file": path.name, "sport": sport, "status": "excluded", "reason": ";".join(reasons)}

    active["file"] = path.name
    active["sport"] = sport
    active["gender"] = gender
    active["test_date"] = test_date
    active["dob"] = dob
    active["age_years"] = age
    active["stage_index"] = np.arange(1, len(active) + 1)
    active["n_active_stages"] = len(active)
    active["baseline_load"] = min_load
    active["baseline_hr"] = hr0
    active["baseline_vo2"] = vo20
    active["hrmax"] = hrmax
    active["vo2max"] = vo2max
    active["max_load"] = max_load
    active["hrr"] = (active["hr"] - hr0) / (hrmax - hr0)
    active["vo2r"] = (active["vo2"] - vo20) / (vo2max - vo20)
    active["load_fraction"] = (active["load"] - min_load) / (max_load - min_load)
    active["baseline_exact_zero"] = bool(min_load == 0)

    # Retain physiologically plausible measurement noise, but exclude gross
    # values that indicate anchor or transcription failure.
    active = active.loc[
        active["hrr"].between(-0.10, 1.15)
        & active["vo2r"].between(-0.10, 1.15)
        & active["load_fraction"].between(0, 1.001)
    ].copy()
    if len(active) < 4:
        return None, {"file": path.name, "sport": sport, "status": "excluded", "reason": "fewer_than_4_plausible_stages"}

    keep = [
        "file", "sport", "gender", "test_date", "dob", "age_years",
        "stage_index", "n_active_stages", "load", "hr", "vo2", "lactate",
        "cadence", "baseline_load", "baseline_hr", "baseline_vo2", "hrmax",
        "vo2max", "max_load", "hrr", "vo2r", "load_fraction",
        "baseline_exact_zero",
    ]
    audit = {
        "file": path.name,
        "sport": sport,
        "status": "included",
        "reason": "",
        "n_stages": len(active),
        "age_years": age,
        "test_date": test_date,
        "baseline_hr": hr0,
        "hrmax": hrmax,
        "baseline_vo2": vo20,
        "vo2max": vo2max,
    }
    return active[keep], audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    summary_path = args.input / "Data_Summary.xlsx"
    summary = pd.read_excel(summary_path)
    summary = summary.set_index(summary["file"].astype(str), drop=False)

    frames = []
    audit_rows = []
    for path in sorted(args.input.glob("A*.xlsx")):
        row = summary.loc[path.name] if path.name in summary.index else None
        try:
            frame, audit = extract_one(path, row)
        except Exception as exc:  # Preserve a complete audit trail.
            frame = None
            audit = {"file": path.name, "status": "excluded", "reason": f"read_error:{type(exc).__name__}:{exc}"}
        audit_rows.append(audit)
        if frame is not None:
            frames.append(frame)

    tidy = pd.concat(frames, ignore_index=True)
    audit = pd.DataFrame(audit_rows)
    tidy.to_csv(args.output / "graded_tests_tidy.csv", index=False)
    audit.to_csv(args.output / "graded_tests_extraction_audit.csv", index=False)

    counts = (
        audit.groupby(["sport", "status"], dropna=False).size().rename("n_tests").reset_index()
    )
    print(counts.to_string(index=False))
    print(f"Included stage rows: {len(tidy):,}")
    print(f"Included tests: {tidy['file'].nunique():,}")


if __name__ == "__main__":
    main()
