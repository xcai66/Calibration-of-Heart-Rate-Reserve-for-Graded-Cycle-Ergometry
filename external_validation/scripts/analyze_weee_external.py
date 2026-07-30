from __future__ import annotations

import ast
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "weee" / "selected"
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"

LAMBDA = 6.2
CENTERS = (np.arange(1, 11, dtype=float) - 0.5) / 10.0
RANDOM_SEED = 20260730
BOOTSTRAP_REPLICATES = 5000
STAGES = {
    "sit": "Start_Sit",
    "stand": "Start_Stand",
    "cycle_low": "Start_Cycle1",
    "cycle_high": "Start_Cycle2",
    "run_low": "Start_Run1",
    "run_high": "Start_Run2",
}


def time_weights(seconds: np.ndarray, cap_seconds: float = 30.0) -> np.ndarray:
    seconds = np.asarray(seconds, dtype=float)
    if len(seconds) < 2:
        return np.zeros(len(seconds), dtype=float)
    intervals = np.diff(seconds)
    valid = intervals[(intervals > 0) & (intervals <= cap_seconds)]
    terminal = float(np.median(valid)) if len(valid) else 1.0
    return np.clip(np.diff(seconds, append=seconds[-1] + terminal), 0.0, cap_seconds)


def score_stage(frame: pd.DataFrame, start: pd.Timestamp, hrrest: float, hrmax: float) -> dict[str, float] | None:
    end = start + pd.Timedelta(seconds=300)
    stage = frame[(frame["time"] >= start) & (frame["time"] < end) & frame["hr"].between(30, 220)].copy()
    stage = stage.sort_values("time").drop_duplicates("time")
    if len(stage) < 3:
        return None
    seconds = (stage["time"] - start).dt.total_seconds().to_numpy(dtype=float)
    weights = time_weights(seconds)
    coverage = float(weights.sum() / 300.0)
    if coverage < 0.80 or hrmax <= hrrest + 20:
        return None
    raw_hrr = (stage["hr"].to_numpy(dtype=float) - hrrest) / (hrmax - hrrest)
    hrr = np.clip(raw_hrr, 0.0, 1.0)
    mean_hrr = float(np.average(hrr, weights=weights))
    bins = np.minimum((hrr * 10).astype(int), 9)
    proportions = np.array([weights[bins == index].sum() for index in range(10)], dtype=float)
    proportions /= proportions.sum()
    exp_weights = np.exp(LAMBDA * CENTERS)
    tilted = float(np.sum(proportions * CENTERS * exp_weights) / np.sum(proportions * exp_weights))
    return {
        "mean_hrr": mean_hrr,
        "thrr_i": tilted,
        "delta_tilt": tilted - mean_hrr,
        "coverage": coverage,
        "below_zero_fraction": float(np.average(raw_hrr < 0, weights=weights)),
        "above_one_fraction": float(np.average(raw_hrr > 1, weights=weights)),
    }


def load_reference(participant: str) -> pd.DataFrame:
    frames = []
    for path in sorted((RAW / participant / "VO2").rglob("DataAverage.csv")):
        frame = pd.read_csv(path)
        if "Time" not in frame or "HR[bpm]" not in frame:
            continue
        frames.append(pd.DataFrame({
            "time": pd.to_datetime(frame["Time"], errors="coerce"),
            "hr": pd.to_numeric(frame["HR[bpm]"], errors="coerce"),
            "vo2_ml_kg_min": pd.to_numeric(frame["VO2[mL/kg/min]"], errors="coerce"),
        }))
    if not frames:
        return pd.DataFrame(columns=["time", "hr", "vo2_ml_kg_min"])
    return pd.concat(frames, ignore_index=True).dropna(subset=["time"]).sort_values("time").drop_duplicates("time")


def load_zephyr(participant: str) -> pd.DataFrame:
    frames = []
    for path in sorted((RAW / participant / "ZEPHYR").glob("*_Summary.csv")):
        frame = pd.read_csv(path, usecols=["Time", "HR"])
        frames.append(pd.DataFrame({
            "time": pd.to_datetime(frame["Time"], format="%d/%m/%Y %H:%M:%S.%f", errors="coerce"),
            "hr": pd.to_numeric(frame["HR"], errors="coerce"),
        }))
    if not frames:
        return pd.DataFrame(columns=["time", "hr"])
    return pd.concat(frames, ignore_index=True).dropna(subset=["time"]).sort_values("time").drop_duplicates("time")


def load_e4(participant: str) -> pd.DataFrame:
    path = RAW / participant / "E4" / "HR.csv"
    if not path.exists():
        return pd.DataFrame(columns=["time", "hr"])
    values = pd.read_csv(path, header=None)[0].to_numpy(dtype=float)
    if len(values) < 3:
        return pd.DataFrame(columns=["time", "hr"])
    start_epoch, rate = values[0], values[1]
    hr = values[2:]
    times = pd.to_datetime(start_epoch + np.arange(len(hr)) / rate, unit="s", utc=True).tz_convert("Europe/Zurich").tz_localize(None)
    return pd.DataFrame({"time": times, "hr": hr})


def load_apple() -> pd.DataFrame:
    path = RAW / "Apple watch" / "HealthAutoExport.csv"
    csv.field_size_limit(sys.maxsize)
    metrics = None
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.reader(handle):
            if row and row[0] == "metrics":
                metrics = ast.literal_eval(row[1])
                break
    if metrics is None:
        return pd.DataFrame(columns=["time", "hr"])
    heart_rate = next(item for item in metrics if item.get("name") == "heart_rate")
    frame = pd.DataFrame(heart_rate["data"])
    time = pd.to_datetime(frame["date"], utc=True).dt.tz_convert("Europe/Zurich").dt.tz_localize(None)
    hr_column = "Avg" if "Avg" in frame.columns else "qty"
    return pd.DataFrame({"time": time, "hr": pd.to_numeric(frame[hr_column], errors="coerce")}).sort_values("time").drop_duplicates("time")


def stage_vo2(reference: pd.DataFrame, start: pd.Timestamp) -> tuple[float, float] | None:
    end = start + pd.Timedelta(seconds=300)
    stage = reference[(reference["time"] >= start) & (reference["time"] < end) & (reference["vo2_ml_kg_min"] > 0)].copy()
    stage = stage.sort_values("time").drop_duplicates("time")
    if len(stage) < 30:
        return None
    seconds = (stage["time"] - start).dt.total_seconds().to_numpy(dtype=float)
    weights = time_weights(seconds)
    coverage = float(weights.sum() / 300.0)
    if coverage < 0.80:
        return None
    return float(np.average(stage["vo2_ml_kg_min"].to_numpy(dtype=float), weights=weights)), coverage


def fit_ols(frame: pd.DataFrame, features: list[str], target: str) -> np.ndarray:
    x = np.column_stack([np.ones(len(frame)), frame[features].to_numpy(dtype=float)])
    return np.linalg.lstsq(x, frame[target].to_numpy(dtype=float), rcond=None)[0]


def predict_ols(frame: pd.DataFrame, features: list[str], coefficients: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones(len(frame)), frame[features].to_numpy(dtype=float)]) @ coefficients


def leave_one_participant_out(frame: pd.DataFrame, features: list[str], target: str) -> np.ndarray:
    predictions = np.full(len(frame), np.nan)
    for participant in sorted(frame["participant"].unique()):
        test = frame["participant"] == participant
        coefficients = fit_ols(frame.loc[~test], features, target)
        predictions[test] = predict_ols(frame.loc[test], features, coefficients)
    return predictions


def participant_balanced_metrics(frame: pd.DataFrame, prediction: str, target: str, sampled: list[str] | None = None) -> dict[str, float]:
    groups = {participant: group for participant, group in frame.groupby("participant")}
    chosen = list(groups) if sampled is None else sampled
    mae, mse, y_all, pred_all, weights = [], [], [], [], []
    for participant in chosen:
        group = groups[participant]
        error = group[prediction].to_numpy() - group[target].to_numpy()
        mae.append(float(np.mean(np.abs(error))))
        mse.append(float(np.mean(error**2)))
        y_all.extend(group[target])
        pred_all.extend(group[prediction])
        weights.extend(np.repeat(1 / len(group), len(group)))
    y, pred, w = np.asarray(y_all), np.asarray(pred_all), np.asarray(weights)
    center = float(np.average(y, weights=w))
    return {
        "mae": float(np.mean(mae)),
        "rmse": float(np.sqrt(np.mean(mse))),
        "r2": 1 - float(np.sum(w * (y - pred) ** 2)) / float(np.sum(w * (y - center) ** 2)),
    }


def construct_bootstrap(frame: pd.DataFrame, target: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    participants = np.array(sorted(frame["participant"].unique()), dtype=object)
    observed = {model: participant_balanced_metrics(frame, f"pred_{model}", target) for model in ["base", "augmented"]}
    rng = np.random.default_rng(RANDOM_SEED)
    boot = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sample = rng.choice(participants, len(participants), replace=True).tolist()
        base = participant_balanced_metrics(frame, "pred_base", target, sample)
        augmented = participant_balanced_metrics(frame, "pred_augmented", target, sample)
        boot.append({metric: augmented[metric] - base[metric] for metric in base})
    boot = pd.DataFrame(boot)
    summary = pd.DataFrame([{"model": model, "metric": metric, "estimate": value} for model, metrics in observed.items() for metric, value in metrics.items()])
    comparison = pd.DataFrame([{
        "contrast": "augmented_minus_base",
        "metric": metric,
        "estimate": observed["augmented"][metric] - observed["base"][metric],
        "ci_low": float(np.percentile(boot[metric], 2.5)),
        "ci_high": float(np.percentile(boot[metric], 97.5)),
    } for metric in boot.columns])
    return summary, comparison


def construct_rank_association(frame: pd.DataFrame, target: str) -> pd.DataFrame:
    """Exploratory pooled stage-level Spearman associations with participant-cluster CIs."""
    participants = np.array(sorted(frame["participant"].unique()), dtype=object)
    groups = {participant: group for participant, group in frame.groupby("participant")}
    metrics = ["mean_hrr", "thrr_i", "delta_tilt"]
    observed = {metric: float(frame[[metric, target]].corr(method="spearman").iloc[0, 1]) for metric in metrics}
    rng = np.random.default_rng(RANDOM_SEED + 3)
    boot = {metric: [] for metric in metrics}
    boot["thrr_i_minus_mean_hrr"] = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled = rng.choice(participants, len(participants), replace=True)
        sample = pd.concat([groups[participant] for participant in sampled], ignore_index=True)
        values = {metric: float(sample[[metric, target]].corr(method="spearman").iloc[0, 1]) for metric in metrics}
        for metric in metrics:
            boot[metric].append(values[metric])
        boot["thrr_i_minus_mean_hrr"].append(values["thrr_i"] - values["mean_hrr"])
    rows = []
    for metric in metrics:
        rows.append({
            "association": metric,
            "spearman_rho": observed[metric],
            "ci_low": float(np.percentile(boot[metric], 2.5)),
            "ci_high": float(np.percentile(boot[metric], 97.5)),
        })
    rows.append({
        "association": "thrr_i_minus_mean_hrr",
        "spearman_rho": observed["thrr_i"] - observed["mean_hrr"],
        "ci_low": float(np.percentile(boot["thrr_i_minus_mean_hrr"], 2.5)),
        "ci_high": float(np.percentile(boot["thrr_i_minus_mean_hrr"], 97.5)),
    })
    return pd.DataFrame(rows)


def pearson(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    valid = np.isfinite(left) & np.isfinite(right)
    left, right = left[valid], right[valid]
    if len(left) < 3 or np.std(left) <= 0 or np.std(right) <= 0:
        return np.nan
    return float(np.corrcoef(left, right)[0, 1])


def two_way_residual(frame: pd.DataFrame, column: str) -> np.ndarray:
    participant_dummies = pd.get_dummies(frame["participant"], drop_first=True, dtype=float)
    stage_dummies = pd.get_dummies(frame["stage"], drop_first=True, dtype=float)
    design = np.column_stack([
        np.ones(len(frame)),
        participant_dummies.to_numpy(dtype=float),
        stage_dummies.to_numpy(dtype=float),
    ])
    values = frame[column].to_numpy(dtype=float)
    fitted = design @ np.linalg.lstsq(design, values, rcond=None)[0]
    return values - fitted


def repeated_measures_association(frame: pd.DataFrame, target: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Separate pooled, within-participant, between-participant, and two-way residual associations."""
    metrics = ["mean_hrr", "thrr_i", "delta_tilt"]
    participants = np.asarray(sorted(frame["participant"].unique()), dtype=object)
    groups = {participant: group.copy() for participant, group in frame.groupby("participant")}

    def calculate(sample: pd.DataFrame, metric: str, scale: str) -> float:
        if scale == "pooled_spearman":
            return float(sample[[metric, target]].corr(method="spearman").iloc[0, 1])
        if scale == "within_participant_pearson":
            x = sample[metric] - sample.groupby("participant")[metric].transform("mean")
            y = sample[target] - sample.groupby("participant")[target].transform("mean")
            return pearson(x.to_numpy(), y.to_numpy())
        if scale == "between_participant_pearson":
            means = sample.groupby("participant")[[metric, target]].mean()
            return pearson(means[metric].to_numpy(), means[target].to_numpy())
        if scale == "participant_and_stage_residual_pearson":
            return pearson(two_way_residual(sample, metric), two_way_residual(sample, target))
        raise KeyError(scale)

    scales = [
        "pooled_spearman",
        "within_participant_pearson",
        "between_participant_pearson",
        "participant_and_stage_residual_pearson",
    ]
    observed = {(scale, metric): calculate(frame, metric, scale) for scale in scales for metric in metrics}
    rng = np.random.default_rng(RANDOM_SEED + 4)
    bootstrap = {(scale, metric): [] for scale in scales for metric in metrics}
    bootstrap.update({(scale, "thrr_i_minus_mean_hrr"): [] for scale in scales})
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled_ids = rng.choice(participants, len(participants), replace=True)
        sampled_groups = []
        for copy_index, participant in enumerate(sampled_ids):
            group = groups[participant].copy()
            group["participant"] = f"{participant}__{copy_index}"
            sampled_groups.append(group)
        sample = pd.concat(sampled_groups, ignore_index=True)
        for scale in scales:
            values = {metric: calculate(sample, metric, scale) for metric in metrics}
            for metric in metrics:
                bootstrap[(scale, metric)].append(values[metric])
            bootstrap[(scale, "thrr_i_minus_mean_hrr")].append(values["thrr_i"] - values["mean_hrr"])

    rows = []
    for scale in scales:
        for metric in metrics:
            values = np.asarray(bootstrap[(scale, metric)], dtype=float)
            rows.append({
                "scale": scale,
                "association": metric,
                "estimate": observed[(scale, metric)],
                "ci_low": float(np.nanpercentile(values, 2.5)),
                "ci_high": float(np.nanpercentile(values, 97.5)),
            })
        difference = np.asarray(bootstrap[(scale, "thrr_i_minus_mean_hrr")], dtype=float)
        rows.append({
            "scale": scale,
            "association": "thrr_i_minus_mean_hrr",
            "estimate": observed[(scale, "thrr_i")] - observed[(scale, "mean_hrr")],
            "ci_low": float(np.nanpercentile(difference, 2.5)),
            "ci_high": float(np.nanpercentile(difference, 97.5)),
        })

    participant_rows = []
    for participant, group in frame.groupby("participant"):
        for metric in metrics:
            participant_rows.append({
                "participant": participant,
                "association": metric,
                "stages": len(group),
                "spearman_rho": float(group[[metric, target]].corr(method="spearman").iloc[0, 1]),
            })
    participant_table = pd.DataFrame(participant_rows)
    participant_summary = participant_table.groupby("association").agg(
        participants=("participant", "nunique"),
        median_participant_rho=("spearman_rho", "median"),
        q1_participant_rho=("spearman_rho", lambda value: value.quantile(0.25)),
        q3_participant_rho=("spearman_rho", lambda value: value.quantile(0.75)),
    ).reset_index()
    return pd.DataFrame(rows), participant_table, participant_summary


def icc_absolute(pairs: pd.DataFrame, left: str, right: str) -> float:
    matrix = pairs[[left, right]].to_numpy(dtype=float)
    n, k = matrix.shape
    if n < 3:
        return np.nan
    grand = matrix.mean()
    row_means = matrix.mean(axis=1)
    col_means = matrix.mean(axis=0)
    ms_rows = k * np.sum((row_means - grand) ** 2) / (n - 1)
    ms_cols = n * np.sum((col_means - grand) ** 2) / (k - 1)
    residual = matrix - row_means[:, None] - col_means[None, :] + grand
    ms_error = np.sum(residual**2) / ((n - 1) * (k - 1))
    denominator = ms_rows + (k - 1) * ms_error + k * (ms_cols - ms_error) / n
    return float((ms_rows - ms_error) / denominator) if denominator else np.nan


def device_agreement(pairs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, boot_rows = [], []
    rng = np.random.default_rng(RANDOM_SEED + 1)
    for device in sorted(pairs["device"].unique()):
        device_rows = pairs[pairs["device"] == device]
        participants = np.array(sorted(device_rows["participant"].unique()), dtype=object)
        groups = {participant: group for participant, group in device_rows.groupby("participant")}
        for metric in ["mean_hrr", "thrr_i", "delta_tilt"]:
            difference = device_rows[f"device_{metric}"] - device_rows[f"reference_{metric}"]
            difference_sd = float(difference.std(ddof=1))
            observed = {
                "bias": float(difference.mean()),
                "mae": float(np.abs(difference).mean()),
                "rmse": float(np.sqrt(np.mean(difference**2))),
                "icc_a1": icc_absolute(device_rows, f"reference_{metric}", f"device_{metric}"),
                "loa_lower": float(difference.mean() - 1.96 * difference_sd),
                "loa_upper": float(difference.mean() + 1.96 * difference_sd),
            }
            boot = []
            for _ in range(BOOTSTRAP_REPLICATES):
                sampled = rng.choice(participants, len(participants), replace=True)
                sampled_groups = []
                for copy_index, participant in enumerate(sampled):
                    group = groups[participant].copy()
                    group["participant"] = f"{participant}__{copy_index}"
                    sampled_groups.append(group)
                sample = pd.concat(sampled_groups, ignore_index=True)
                diff = sample[f"device_{metric}"] - sample[f"reference_{metric}"]
                sd = float(diff.std(ddof=1))
                boot.append((
                    float(diff.mean()),
                    float(np.abs(diff).mean()),
                    icc_absolute(sample, f"reference_{metric}", f"device_{metric}"),
                    float(diff.mean() - 1.96 * sd),
                    float(diff.mean() + 1.96 * sd),
                ))
            boot = np.asarray(boot)
            rows.append({"device": device, "score": metric, "participants": len(participants), "stages": len(device_rows), **observed})
            boot_rows.append({
                "device": device,
                "score": metric,
                "bias_ci_low": float(np.percentile(boot[:, 0], 2.5)),
                "bias_ci_high": float(np.percentile(boot[:, 0], 97.5)),
                "mae_ci_low": float(np.percentile(boot[:, 1], 2.5)),
                "mae_ci_high": float(np.percentile(boot[:, 1], 97.5)),
                "icc_a1_ci_low": float(np.nanpercentile(boot[:, 2], 2.5)),
                "icc_a1_ci_high": float(np.nanpercentile(boot[:, 2], 97.5)),
                "loa_lower_ci_low": float(np.nanpercentile(boot[:, 3], 2.5)),
                "loa_lower_ci_high": float(np.nanpercentile(boot[:, 3], 97.5)),
                "loa_upper_ci_low": float(np.nanpercentile(boot[:, 4], 2.5)),
                "loa_upper_ci_high": float(np.nanpercentile(boot[:, 4], 97.5)),
            })
    return pd.DataFrame(rows), pd.DataFrame(boot_rows)


def best_cross_correlation_lag(reference: pd.DataFrame, device: pd.DataFrame, start: pd.Timestamp) -> float:
    end = start + pd.Timedelta(seconds=300)
    ref = reference[(reference["time"] >= start) & (reference["time"] < end)][["time", "hr"]].dropna()
    dev = device[(device["time"] >= start) & (device["time"] < end)][["time", "hr"]].dropna()
    if len(ref) < 60 or len(dev) < 60:
        return np.nan
    grid = pd.date_range(start, end - pd.Timedelta(seconds=1), freq="1s")
    ref_series = ref.set_index("time")["hr"].reindex(ref.set_index("time").index.union(grid)).interpolate("time").reindex(grid)
    dev_series = dev.set_index("time")["hr"].reindex(dev.set_index("time").index.union(grid)).interpolate("time").reindex(grid)
    best_lag, best_r = np.nan, -np.inf
    for lag in range(-15, 16):
        shifted = dev_series.shift(lag)
        valid = ref_series.notna() & shifted.notna()
        if valid.sum() < 60:
            continue
        value = pearson(ref_series[valid].to_numpy(), shifted[valid].to_numpy())
        if np.isfinite(value) and value > best_r:
            best_lag, best_r = float(lag), value
    return best_lag


def synchronization_audit(study: pd.DataFrame, valid_pairs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    apple = load_apple()
    valid_keys = set(zip(valid_pairs["participant"], valid_pairs["stage"], valid_pairs["device"]))
    for participant in sorted(study.index):
        reference = load_reference(participant)
        devices = {"zephyr": load_zephyr(participant), "e4": load_e4(participant), "apple_watch": apple}
        for stage, column in STAGES.items():
            start = pd.Timestamp(study.loc[participant, column])
            end = start + pd.Timedelta(seconds=300)
            ref_times = reference.loc[(reference["time"] >= start) & (reference["time"] < end), "time"].sort_values()
            if ref_times.empty:
                continue
            ref_ns = ref_times.astype("int64").to_numpy()
            for device_name, device in devices.items():
                if (participant, stage, device_name) not in valid_keys:
                    continue
                dev_times = device.loc[(device["time"] >= start) & (device["time"] < end), "time"].sort_values()
                if len(dev_times) < 3:
                    continue
                dev_ns = dev_times.astype("int64").to_numpy()
                position = np.searchsorted(ref_ns, dev_ns)
                left = np.clip(position - 1, 0, len(ref_ns) - 1)
                right = np.clip(position, 0, len(ref_ns) - 1)
                left_diff = dev_ns - ref_ns[left]
                right_diff = dev_ns - ref_ns[right]
                nearest = np.where(np.abs(left_diff) <= np.abs(right_diff), left_diff, right_diff) / 1e9
                matched = np.abs(nearest) <= 2.0
                rows.append({
                    "participant": participant,
                    "stage": stage,
                    "device": device_name,
                    "device_samples": len(dev_times),
                    "timestamp_samples_matched_within_2s_percent": float(100.0 * matched.mean()),
                    "median_signed_nearest_timestamp_offset_s": float(np.median(nearest[matched])) if matched.any() else np.nan,
                    "median_absolute_nearest_timestamp_offset_s": float(np.median(np.abs(nearest[matched]))) if matched.any() else np.nan,
                    "p95_absolute_nearest_timestamp_offset_s": float(np.percentile(np.abs(nearest[matched]), 95)) if matched.any() else np.nan,
                    "optimal_hr_cross_correlation_lag_s": best_cross_correlation_lag(reference, device, start),
                })
    return pd.DataFrame(rows)


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    study = pd.read_csv(RAW / "Study_Information.csv").set_index("Participant")
    demographics = pd.read_csv(RAW / "Demographics.csv").set_index("Participant")
    apple = load_apple()

    construct_rows, score_rows, qc_rows = [], [], []
    for participant in sorted(study.index):
        reference = load_reference(participant)
        if reference.empty:
            qc_rows.append({"participant": participant, "reason": "reference_data_missing"})
            continue
        starts = {stage: pd.Timestamp(study.loc[participant, column]) for stage, column in STAGES.items()}
        sitting = reference[(reference["time"] >= starts["sit"]) & (reference["time"] < starts["sit"] + pd.Timedelta(seconds=300))]
        sitting_hr = sitting.loc[sitting["hr"].between(30, 220), "hr"]
        if len(sitting_hr) < 60:
            qc_rows.append({"participant": participant, "reason": "sitting_anchor_missing"})
            continue
        hrrest = float(sitting_hr.median())
        age = float(demographics.loc[participant, "Age"])
        hrmax = 208.0 - 0.7 * age
        devices = {"zephyr": load_zephyr(participant), "e4": load_e4(participant), "apple_watch": apple}
        for stage, start in starts.items():
            reference_score = score_stage(reference[["time", "hr"]], start, hrrest, hrmax)
            vo2 = stage_vo2(reference, start)
            if reference_score is None or vo2 is None:
                qc_rows.append({"participant": participant, "stage": stage, "reason": "reference_hr_or_vo2_stage_failed_qc"})
                continue
            construct_rows.append({
                "participant": participant,
                "stage": stage,
                "age_years": age,
                "sex_female": int(str(demographics.loc[participant, "Gender"]).upper() == "F"),
                "weight_kg": float(demographics.loc[participant, "Weight"]),
                "hrrest_bpm": hrrest,
                "predicted_hrmax_bpm": hrmax,
                "vo2_ml_kg_min": vo2[0],
                "vo2_coverage": vo2[1],
                **reference_score,
            })
            for device, signal in devices.items():
                device_score = score_stage(signal, start, hrrest, hrmax)
                if device_score is None:
                    continue
                row = {"participant": participant, "stage": stage, "device": device}
                row.update({f"reference_{key}": reference_score[key] for key in ["mean_hrr", "thrr_i", "delta_tilt"]})
                row.update({f"device_{key}": device_score[key] for key in ["mean_hrr", "thrr_i", "delta_tilt"]})
                row["device_coverage"] = device_score["coverage"]
                score_rows.append(row)

    construct = pd.DataFrame(construct_rows)
    pairs = pd.DataFrame(score_rows)
    base_features = ["mean_hrr", "age_years", "sex_female", "weight_kg"]
    augmented_features = base_features + ["delta_tilt"]
    construct["pred_base"] = leave_one_participant_out(construct, base_features, "vo2_ml_kg_min")
    construct["pred_augmented"] = leave_one_participant_out(construct, augmented_features, "vo2_ml_kg_min")
    construct_performance, construct_comparison = construct_bootstrap(construct, "vo2_ml_kg_min")
    rank_association = construct_rank_association(construct, "vo2_ml_kg_min")
    repeated_association, participant_association, participant_association_summary = repeated_measures_association(construct, "vo2_ml_kg_min")
    agreement, agreement_ci = device_agreement(pairs)
    synchronization = synchronization_audit(study, pairs)
    qc = pd.DataFrame(qc_rows)

    summary = {
        "dataset": "WEEE",
        "doi": "10.5281/zenodo.6420886",
        "participants_with_construct_data": int(construct["participant"].nunique()),
        "construct_stages": int(len(construct)),
        "device_pairs": int(len(pairs)),
        "device_participants": {device: int(group["participant"].nunique()) for device, group in pairs.groupby("device")},
        "lambda_locked": LAMBDA,
        "construct_performance": construct_performance.to_dict("records"),
        "construct_comparison": construct_comparison.to_dict("records"),
        "construct_rank_association": rank_association.to_dict("records"),
        "repeated_measures_association": repeated_association.to_dict("records"),
        "participant_specific_association_summary": participant_association_summary.to_dict("records"),
        "device_agreement": agreement.to_dict("records"),
        "device_agreement_intervals": agreement_ci.to_dict("records"),
        "synchronization_audit": synchronization.groupby("device").agg(
            stages=("stage", "size"),
            median_samples_matched_within_2s_percent=("timestamp_samples_matched_within_2s_percent", "median"),
            median_absolute_timestamp_offset_s=("median_absolute_nearest_timestamp_offset_s", "median"),
            p95_absolute_timestamp_offset_s=("p95_absolute_nearest_timestamp_offset_s", "max"),
            median_optimal_hr_lag_s=("optimal_hr_cross_correlation_lag_s", "median"),
        ).reset_index().to_dict("records"),
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
    }

    construct.to_csv(PROCESSED / "weee_construct_stage_metrics.csv", index=False)
    pairs.to_csv(PROCESSED / "weee_device_stage_pairs.csv", index=False)
    qc.to_csv(RESULTS / "weee_qc_exclusions.csv", index=False)
    construct_performance.to_csv(RESULTS / "weee_construct_performance.csv", index=False)
    construct_comparison.to_csv(RESULTS / "weee_construct_comparison.csv", index=False)
    rank_association.to_csv(RESULTS / "weee_construct_rank_association.csv", index=False)
    repeated_association.to_csv(RESULTS / "weee_repeated_measures_association.csv", index=False)
    participant_association.to_csv(RESULTS / "weee_participant_specific_association.csv", index=False)
    participant_association_summary.to_csv(RESULTS / "weee_participant_specific_association_summary.csv", index=False)
    agreement.to_csv(RESULTS / "weee_device_agreement.csv", index=False)
    agreement_ci.to_csv(RESULTS / "weee_device_agreement_intervals.csv", index=False)
    synchronization.to_csv(RESULTS / "weee_synchronization_audit.csv", index=False)
    (RESULTS / "weee_external_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
