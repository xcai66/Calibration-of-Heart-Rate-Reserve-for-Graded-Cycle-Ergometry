from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_malaga_external import (
    LAMBDA,
    grouped_predictions,
    rolling_median,
    time_weights,
    weighted_scores,
)

# Match the primary external-analysis participant bootstrap so the identical
# 180-second specification has one canonical Monte Carlo interval everywhere.
RANDOM_SEED = 20260731
BOOTSTRAP_REPLICATES = 5000


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "malaga"
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"


def recovery_endpoint(
    test: pd.DataFrame,
    effort_start: float,
    effort_end: float,
    window_seconds: int,
    baseline_method: str,
    smoothing_seconds: int = 15,
) -> float:
    recovery = test[(test["time"] > effort_end) & (test["time"] <= effort_end + window_seconds)].copy()
    recovery = recovery.dropna(subset=["time", "VO2"])
    recovery = recovery[(recovery["VO2"] > 0) & np.isfinite(recovery["VO2"])]
    recovery = recovery.sort_values("time").drop_duplicates("time")
    if len(recovery) < 15 or recovery["time"].max() - recovery["time"].min() < window_seconds - 10:
        return np.nan
    smoothed_series = rolling_median(
        recovery["VO2"], recovery["time"], smoothing_seconds, max(2, smoothing_seconds // 5)
    )
    valid = np.isfinite(smoothed_series.to_numpy(dtype=float))
    times = recovery.loc[valid, "time"].to_numpy(dtype=float)
    smoothed = smoothed_series.to_numpy(dtype=float)[valid]
    if len(times) < 10:
        return np.nan
    if baseline_method == "recovery_min":
        baseline = float(np.min(smoothed))
    elif baseline_method == "recovery_final30_median":
        final = smoothed[times >= effort_end + window_seconds - 30]
        baseline = float(np.median(final)) if len(final) else np.nan
    elif baseline_method == "pre_effort_rolling30_min":
        pre = test[(test["time"] >= effort_start - 60) & (test["time"] <= effort_start)].dropna(subset=["VO2"])
        pre = pre[pre["VO2"] > 0].sort_values("time").drop_duplicates("time")
        if len(pre) < 10:
            return np.nan
        pre_smoothed = rolling_median(pre["VO2"], pre["time"], 30, 5).to_numpy(dtype=float)
        baseline = float(np.nanmin(pre_smoothed)) if np.isfinite(pre_smoothed).any() else np.nan
    else:
        raise KeyError(baseline_method)
    if not np.isfinite(baseline):
        return np.nan
    excess = np.maximum(smoothed - baseline, 0.0)
    return float(np.trapezoid(excess, times) / 60.0)


def alternative_hr_scores(test: pd.DataFrame, row: pd.Series, anchor_method: str) -> dict[str, float]:
    effort_start = float(row["effort_start_s"])
    effort_end = float(row["effort_end_s"])
    pre = test[(test["time"] <= effort_start) & test["HR"].between(30, 220)].copy()
    effort = test[(test["time"] >= effort_start) & (test["time"] <= effort_end) & test["HR"].between(30, 220)].copy()
    effort = effort.sort_values("time").drop_duplicates("time")
    if len(pre) < 10 or len(effort) < 20:
        return {}
    if anchor_method == "pre_rolling30_min":
        anchor_values = rolling_median(pre["HR"], pre["time"], 30, 5).to_numpy(dtype=float)
        lower_anchor = float(np.nanmin(anchor_values)) if np.isfinite(anchor_values).any() else np.nan
    elif anchor_method == "first60_median":
        first = pre[pre["time"] <= pre["time"].min() + 60]
        lower_anchor = float(first["HR"].median())
    elif anchor_method == "pre_median":
        lower_anchor = float(pre["HR"].median())
    else:
        raise KeyError(anchor_method)
    hrmax = float(effort["HR"].max())
    if not np.isfinite(lower_anchor) or hrmax <= lower_anchor + 30:
        return {}
    weights = time_weights(effort["time"].to_numpy(dtype=float))
    hrr = (effort["HR"].to_numpy(dtype=float) - lower_anchor) / (hrmax - lower_anchor)
    scores = weighted_scores(hrr, weights)
    return {"mean_hrr": scores["mean_hrr"], "delta_tilt": scores["delta_tilt"], "lower_anchor_bpm": lower_anchor}


def evaluate(frame: pd.DataFrame, target: str, label: str) -> tuple[dict, dict]:
    complete = frame.dropna(subset=[target, "mean_hrr", "delta_tilt", "effort_duration_min", "age_years", "sex_female", "weight_kg"]).copy()
    base_features = ["effort_duration_min", "mean_hrr", "age_years", "sex_female", "weight_kg"]
    augmented_features = base_features + ["delta_tilt"]
    complete["pred_base"] = grouped_predictions(complete, base_features, target)
    complete["pred_augmented"] = grouped_predictions(complete, augmented_features, target)
    participant_rows = []
    for participant, group in complete.groupby("participant"):
        participant_rows.append({
            "participant": participant,
            "base_mae": float(np.mean(np.abs(group["pred_base"] - group[target]))),
            "augmented_mae": float(np.mean(np.abs(group["pred_augmented"] - group[target]))),
        })
    participant_table = pd.DataFrame(participant_rows)
    differences = (participant_table["augmented_mae"] - participant_table["base_mae"]).to_numpy(dtype=float)
    rng = np.random.default_rng(RANDOM_SEED)
    bootstrap = np.asarray([
        rng.choice(differences, len(differences), replace=True).mean()
        for _ in range(BOOTSTRAP_REPLICATES)
    ])
    summary = {
        "analysis": label,
        "tests": int(len(complete)),
        "participants": int(complete["participant"].nunique()),
        "base_mae": float(participant_table["base_mae"].mean()),
        "augmented_mae": float(participant_table["augmented_mae"].mean()),
        "mae_difference_augmented_minus_base": float(differences.mean()),
        "ci_low": float(np.percentile(bootstrap, 2.5)),
        "ci_high": float(np.percentile(bootstrap, 97.5)),
    }
    return summary, complete


def main() -> None:
    base = pd.read_csv(PROCESSED / "malaga_external_test_metrics.csv", dtype={"participant": str, "test_id": str})
    measures = pd.read_csv(RAW / "test_measure.csv", dtype={"ID_test": str})
    tests = {test_id: group.sort_values("time").drop_duplicates("time") for test_id, group in measures.groupby("ID_test", sort=False)}

    endpoint_rows = []
    endpoint_frames = []
    endpoint_specs = []
    for window in [60, 120, 180]:
        for baseline_method in ["recovery_min", "recovery_final30_median", "pre_effort_rolling30_min"]:
            endpoint_specs.append((window, baseline_method, 15))
    endpoint_specs.extend([(180, "recovery_final30_median", 5), (180, "recovery_final30_median", 30)])
    for window, baseline_method, smoothing in endpoint_specs:
        label = f"recovery_{window}s__{baseline_method}__smooth_{smoothing}s"
        working = base.copy()
        working[label] = [
            recovery_endpoint(tests[row.test_id], row.effort_start_s, row.effort_end_s, window, baseline_method, smoothing)
            if row.test_id in tests else np.nan
            for row in working.itertuples()
        ]
        summary, complete = evaluate(working, label, label)
        summary.update({"window_seconds": window, "baseline_method": baseline_method, "smoothing_seconds": smoothing})
        endpoint_rows.append(summary)
        endpoint_frames.append(complete[["participant", "test_id", label]].rename(columns={label: "endpoint_ml"}).assign(analysis=label))

    anchor_rows = []
    anchor_frames = []
    for anchor_method in ["pre_rolling30_min", "first60_median", "pre_median"]:
        working = base.copy()
        values = [
            alternative_hr_scores(tests[row.test_id], pd.Series(row._asdict()), anchor_method)
            if row.test_id in tests else {}
            for row in working.itertuples()
        ]
        working["mean_hrr"] = [value.get("mean_hrr", np.nan) for value in values]
        working["delta_tilt"] = [value.get("delta_tilt", np.nan) for value in values]
        working["lower_anchor_sensitivity_bpm"] = [value.get("lower_anchor_bpm", np.nan) for value in values]
        label = f"hr_lower_anchor__{anchor_method}"
        summary, complete = evaluate(working, "epoc_180_ml", label)
        summary["hr_anchor_method"] = anchor_method
        anchor_rows.append(summary)
        anchor_frames.append(complete[["participant", "test_id", "mean_hrr", "delta_tilt", "lower_anchor_sensitivity_bpm"]].assign(analysis=label))

    endpoint_table = pd.DataFrame(endpoint_rows)
    anchor_table = pd.DataFrame(anchor_rows)
    endpoint_table.to_csv(RESULTS / "malaga_recovery_endpoint_sensitivity.csv", index=False)
    anchor_table.to_csv(RESULTS / "malaga_hr_anchor_sensitivity.csv", index=False)
    pd.concat(endpoint_frames, ignore_index=True).to_csv(PROCESSED / "malaga_recovery_endpoint_sensitivity_values.csv", index=False)
    pd.concat(anchor_frames, ignore_index=True).to_csv(PROCESSED / "malaga_hr_anchor_sensitivity_values.csv", index=False)
    payload = {
        "lambda_locked": LAMBDA,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "endpoint_sensitivity": endpoint_table.to_dict("records"),
        "hr_anchor_sensitivity": anchor_table.to_dict("records"),
        "interpretation": "All recovery definitions and lower-anchor alternatives were reported. None was selected on the basis of direction or nominal favorability.",
    }
    (RESULTS / "malaga_sensitivity_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
