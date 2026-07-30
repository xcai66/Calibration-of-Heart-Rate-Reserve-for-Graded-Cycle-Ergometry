from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "malaga"
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
MANIFESTS = ROOT / "manifests"

LAMBDA = 6.2
CENTERS = (np.arange(1, 11, dtype=float) - 0.5) / 10.0
RANDOM_SEED = 20260730
BOOTSTRAP_REPLICATES = 5000
FOLDS = 10


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rolling_median(values: pd.Series, times: pd.Series, seconds: int, min_periods: int) -> pd.Series:
    index = pd.to_timedelta(times.to_numpy(dtype=float), unit="s")
    series = pd.Series(values.to_numpy(dtype=float), index=index)
    return series.rolling(f"{seconds}s", min_periods=min_periods).median()


def time_weights(times: np.ndarray, cap_seconds: float = 30.0) -> np.ndarray:
    times = np.asarray(times, dtype=float)
    if len(times) < 2:
        return np.zeros_like(times)
    intervals = np.diff(times)
    valid = intervals[(intervals > 0) & (intervals <= cap_seconds)]
    terminal = float(np.median(valid)) if len(valid) else 2.0
    return np.clip(np.diff(times, append=times[-1] + terminal), 0.0, cap_seconds)


def weighted_scores(hrr: np.ndarray, weights: np.ndarray) -> dict[str, float]:
    hrr = np.clip(np.asarray(hrr, dtype=float), 0.0, 1.0)
    weights = np.asarray(weights, dtype=float)
    mean_hrr = float(np.average(hrr, weights=weights))
    bins = np.minimum((hrr * 10).astype(int), 9)
    seconds = np.array([weights[bins == i].sum() for i in range(10)], dtype=float)
    proportions = seconds / seconds.sum()
    exp_weights = np.exp(LAMBDA * CENTERS)
    tilted = float(np.sum(proportions * CENTERS * exp_weights) / np.sum(proportions * exp_weights))
    linear = float(np.sum(proportions * np.arange(1, 11, dtype=float)))
    output = {
        "mean_hrr": mean_hrr,
        "thrr_i": tilted,
        "delta_tilt": tilted - mean_hrr,
        "linear_decile": linear,
    }
    output.update({f"p{i + 1}": float(proportions[i]) for i in range(10)})
    return output


def integrate_recovery(recovery: pd.DataFrame, weight_kg: float) -> dict[str, float]:
    recovery = recovery.dropna(subset=["time", "VO2"]).copy()
    recovery = recovery[(recovery["VO2"] > 0) & np.isfinite(recovery["VO2"])]
    recovery = recovery.sort_values("time").drop_duplicates("time")
    if len(recovery) < 20:
        return {}
    smoothed = rolling_median(recovery["VO2"], recovery["time"], 15, 3).to_numpy(dtype=float)
    valid = np.isfinite(smoothed)
    times = recovery.loc[valid, "time"].to_numpy(dtype=float)
    smoothed = smoothed[valid]
    if len(times) < 20 or (times.max() - times.min()) < 170:
        return {}
    baseline = float(np.min(smoothed))
    excess = np.maximum(smoothed - baseline, 0.0)
    epoc_ml = float(np.trapezoid(excess, times) / 60.0)
    ratio = recovery["VCO2"].to_numpy(dtype=float) / recovery["VO2"].to_numpy(dtype=float)
    return {
        "recovery_vo2_baseline_ml_min": baseline,
        "epoc_180_ml": epoc_ml,
        "epoc_180_ml_kg": epoc_ml / weight_kg if weight_kg > 0 else np.nan,
        "recovery_peak_rer": float(np.nanpercentile(ratio[np.isfinite(ratio)], 95)) if np.isfinite(ratio).any() else np.nan,
    }


def summarize_test(test: pd.DataFrame, info: pd.Series) -> tuple[dict, str]:
    test = test.sort_values("time").drop_duplicates("time").copy()
    effort_mask = test["Speed"] > 5.05
    if not effort_mask.any():
        return {}, "no_effort_phase"
    effort_start = float(test.loc[effort_mask, "time"].min())
    effort_end = float(test.loc[effort_mask, "time"].max())
    record_end = float(test["time"].max())
    if effort_start < 60:
        return {}, "pre_effort_shorter_than_60s"
    if record_end - effort_end < 180:
        return {}, "recovery_shorter_than_180s"

    pre = test[(test["time"] <= effort_start) & test["HR"].between(30, 220)].copy()
    rolling = rolling_median(pre["HR"], pre["time"], 30, 5)
    if not np.isfinite(rolling).any():
        return {}, "lower_anchor_unavailable"
    lower_anchor = float(np.nanmin(rolling))

    effort = test[(test["time"] >= effort_start) & (test["time"] <= effort_end)].copy()
    effort = effort[effort["HR"].between(30, 220)].sort_values("time").drop_duplicates("time")
    if len(effort) < 20:
        return {}, "insufficient_effort_hr"
    duration = effort_end - effort_start
    weights = time_weights(effort["time"].to_numpy(dtype=float))
    coverage = float(weights.sum() / duration) if duration > 0 else 0.0
    if coverage < 0.80:
        return {}, "effort_hr_coverage_below_80pct"
    hrmax = float(effort["HR"].max())
    if hrmax - lower_anchor < 30:
        return {}, "hr_anchor_range_below_30bpm"

    raw_hrr = (effort["HR"].to_numpy(dtype=float) - lower_anchor) / (hrmax - lower_anchor)
    scores = weighted_scores(raw_hrr, weights)
    recovery = test[(test["time"] > effort_end) & (test["time"] <= effort_end + 180)].copy()
    recovery_values = integrate_recovery(recovery, float(info["Weight"]))
    if not recovery_values:
        return {}, "recovery_vo2_unavailable"

    pre_hr = float(pre["HR"].iloc[-1]) if len(pre) else np.nan
    at_60 = recovery.iloc[(recovery["time"] - (effort_end + 60)).abs().argsort()[:1]]
    hr_60 = float(at_60["HR"].iloc[0]) if len(at_60) and pd.notna(at_60["HR"].iloc[0]) else np.nan
    result = {
        "participant": str(int(info["ID"])),
        "test_id": str(info.name),
        "age_years": float(info["Age"]),
        "weight_kg": float(info["Weight"]),
        "height_cm": float(info["Height"]),
        "sex_female": int(info["Sex"] == 1),
        "effort_start_s": effort_start,
        "effort_end_s": effort_end,
        "effort_duration_min": duration / 60.0,
        "recovery_available_s": record_end - effort_end,
        "lower_anchor_bpm": lower_anchor,
        "effort_hrmax_bpm": hrmax,
        "effort_hr_coverage": coverage,
        "hrr_below_zero_fraction": float(np.average(raw_hrr < 0, weights=weights)),
        "hrr_above_one_fraction": float(np.average(raw_hrr > 1, weights=weights)),
        "hr_recovery_60_bpm": hrmax - hr_60 if np.isfinite(hr_60) else np.nan,
        "effort_peak_vo2_ml_min": float(np.nanmax(effort["VO2"])) if effort["VO2"].notna().any() else np.nan,
        "effort_peak_rer": float(np.nanpercentile((effort["VCO2"] / effort["VO2"]).replace([np.inf, -np.inf], np.nan).dropna(), 95)) if effort["VO2"].notna().any() else np.nan,
    }
    result.update(scores)
    result.update(recovery_values)
    return result, "included"


def fit_ols(train: pd.DataFrame, features: list[str], target: str) -> np.ndarray:
    x = train[features].to_numpy(dtype=float)
    x = np.column_stack([np.ones(len(x)), x])
    return np.linalg.lstsq(x, train[target].to_numpy(dtype=float), rcond=None)[0]


def predict_ols(frame: pd.DataFrame, features: list[str], coefficients: np.ndarray) -> np.ndarray:
    x = frame[features].to_numpy(dtype=float)
    return np.column_stack([np.ones(len(x)), x]) @ coefficients


def grouped_predictions(frame: pd.DataFrame, features: list[str], target: str) -> np.ndarray:
    participants = np.array(sorted(frame["participant"].unique()), dtype=object)
    rng = np.random.default_rng(RANDOM_SEED)
    rng.shuffle(participants)
    fold_map = {participant: index % FOLDS for index, participant in enumerate(participants)}
    prediction = np.full(len(frame), np.nan)
    for fold in range(FOLDS):
        test_mask = frame["participant"].map(fold_map).to_numpy() == fold
        coefficients = fit_ols(frame.loc[~test_mask], features, target)
        prediction[test_mask] = predict_ols(frame.loc[test_mask], features, coefficients)
    return prediction


def weighted_metrics(frame: pd.DataFrame, prediction: str, target: str, participants: list[str] | None = None) -> dict[str, float]:
    groups = {str(participant): group for participant, group in frame.groupby("participant")}
    chosen = list(groups) if participants is None else participants
    absolute, squared, observed, predicted, weights = [], [], [], [], []
    for participant in chosen:
        group = groups[str(participant)]
        error = group[prediction].to_numpy(dtype=float) - group[target].to_numpy(dtype=float)
        absolute.append(float(np.mean(np.abs(error))))
        squared.append(float(np.mean(error**2)))
        observed.extend(group[target].to_numpy(dtype=float))
        predicted.extend(group[prediction].to_numpy(dtype=float))
        weights.extend(np.repeat(1.0 / len(group), len(group)))
    y = np.asarray(observed)
    pred = np.asarray(predicted)
    w = np.asarray(weights)
    center = float(np.average(y, weights=w))
    denominator = float(np.sum(w * (y - center) ** 2))
    return {
        "participant_balanced_mae": float(np.mean(absolute)),
        "participant_balanced_rmse": float(np.sqrt(np.mean(squared))),
        "participant_balanced_r2": 1.0 - float(np.sum(w * (y - pred) ** 2)) / denominator,
    }


def cluster_bootstrap(frame: pd.DataFrame, target: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(RANDOM_SEED + 1)
    participants = np.array(sorted(frame["participant"].unique()), dtype=object)
    observed_base = weighted_metrics(frame, "pred_base", target)
    observed_aug = weighted_metrics(frame, "pred_augmented", target)
    boot = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled = rng.choice(participants, len(participants), replace=True).tolist()
        base = weighted_metrics(frame, "pred_base", target, sampled)
        aug = weighted_metrics(frame, "pred_augmented", target, sampled)
        boot.append({key: aug[key] - base[key] for key in base})
    boot = pd.DataFrame(boot)
    summary = []
    for model, metrics in [("base", observed_base), ("augmented", observed_aug)]:
        for metric, value in metrics.items():
            summary.append({"model": model, "metric": metric, "estimate": value})
    comparisons = []
    for metric in boot.columns:
        comparisons.append({
            "contrast": "augmented_minus_base",
            "metric": metric,
            "estimate": observed_aug[metric] - observed_base[metric],
            "ci_low": float(np.percentile(boot[metric], 2.5)),
            "ci_high": float(np.percentile(boot[metric], 97.5)),
        })
    return pd.DataFrame(summary), pd.DataFrame(comparisons)


def coefficient_bootstrap(frame: pd.DataFrame, features: list[str], target: str) -> dict[str, float]:
    participants = np.array(sorted(frame["participant"].unique()), dtype=object)
    groups = {str(participant): group for participant, group in frame.groupby("participant")}
    observed = fit_ols(frame, features, target)[features.index("delta_tilt") + 1]
    rng = np.random.default_rng(RANDOM_SEED + 2)
    values = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled = rng.choice(participants, len(participants), replace=True)
        sample = pd.concat([groups[str(participant)] for participant in sampled], ignore_index=True)
        values.append(fit_ols(sample, features, target)[features.index("delta_tilt") + 1])
    return {
        "delta_tilt_coefficient_per_hrr_unit_ml": float(observed),
        "delta_tilt_coefficient_per_0_01_hrr_ml": float(observed / 100.0),
        "ci_low_per_0_01_hrr_ml": float(np.percentile(values, 2.5) / 100.0),
        "ci_high_per_0_01_hrr_ml": float(np.percentile(values, 97.5) / 100.0),
    }


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    MANIFESTS.mkdir(parents=True, exist_ok=True)

    subject_path = RAW / "subject-info.csv"
    measure_path = RAW / "test_measure.csv"
    subjects = pd.read_csv(subject_path)
    measures = pd.read_csv(measure_path)
    subject_map = subjects.set_index("ID_test")

    included, qc_rows = [], []
    for test_id, test in measures.groupby("ID_test", sort=False):
        if test_id not in subject_map.index:
            qc_rows.append({"test_id": test_id, "status": "excluded", "reason": "subject_metadata_missing"})
            continue
        summary, reason = summarize_test(test, subject_map.loc[test_id])
        qc_rows.append({"test_id": test_id, "participant": str(int(test["ID"].iloc[0])), "status": "included" if reason == "included" else "excluded", "reason": reason})
        if summary:
            included.append(summary)

    frame = pd.DataFrame(included).sort_values(["participant", "test_id"]).reset_index(drop=True)
    qc = pd.DataFrame(qc_rows)
    target = "epoc_180_ml"
    base_features = ["effort_duration_min", "mean_hrr", "age_years", "sex_female", "weight_kg"]
    augmented_features = base_features + ["delta_tilt"]
    frame["pred_base"] = grouped_predictions(frame, base_features, target)
    frame["pred_augmented"] = grouped_predictions(frame, augmented_features, target)

    performance, comparison = cluster_bootstrap(frame, target)
    coefficient = coefficient_bootstrap(frame, augmented_features, target)
    qc_summary = qc.groupby(["status", "reason"], dropna=False).size().reset_index(name="tests")

    manifest = {
        "dataset": "Treadmill Maximal Exercise Tests from the University of Malaga",
        "version": "1.0.1",
        "doi": "10.13026/7ezk-j442",
        "source_url": "https://physionet.org/content/treadmill-exercise-cardioresp/1.0.1/",
        "access_date": "2026-07-30",
        "files": [
            {"name": subject_path.name, "bytes": subject_path.stat().st_size, "sha256": sha256(subject_path)},
            {"name": measure_path.name, "bytes": measure_path.stat().st_size, "sha256": sha256(measure_path)},
        ],
        "license_file": "LICENSE.txt",
    }

    summary = {
        "formula": "ten-bin normalized exponential tilt",
        "lambda_locked": LAMBDA,
        "tests_screened": int(qc["test_id"].nunique()),
        "tests_included": int(len(frame)),
        "participants_included": int(frame["participant"].nunique()),
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "grouped_folds": FOLDS,
        "performance": performance.to_dict("records"),
        "comparison": comparison.to_dict("records"),
        "coefficient": coefficient,
        "median_delta_tilt": float(frame["delta_tilt"].median()),
        "median_epoc_180_ml": float(frame[target].median()),
        "hrr_out_of_range": {
            "median_below_zero_fraction": float(frame["hrr_below_zero_fraction"].median()),
            "median_above_one_fraction": float(frame["hrr_above_one_fraction"].median()),
        },
    }

    frame.to_csv(PROCESSED / "malaga_external_test_metrics.csv", index=False)
    qc.to_csv(RESULTS / "malaga_qc_by_test.csv", index=False)
    qc_summary.to_csv(RESULTS / "malaga_qc_summary.csv", index=False)
    performance.to_csv(RESULTS / "malaga_model_performance.csv", index=False)
    comparison.to_csv(RESULTS / "malaga_model_comparison.csv", index=False)
    (RESULTS / "malaga_external_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (MANIFESTS / "malaga_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
