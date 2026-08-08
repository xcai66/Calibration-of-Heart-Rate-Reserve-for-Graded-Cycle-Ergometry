#!/usr/bin/env python3
"""Locked validation of the cycle-ergometry-derived HRR transfer function.

Primary internal validation uses the latest 30% of cycling tests, untouched
during sport/model selection. External validation uses ACTES (PhysioNet), with
participants as analysis units. The locked parameters are tau=0.90 and
kappa=5.75; this script never re-optimizes them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


TAU = 0.90
KAPPA = 5.75
SEED = 20260808


def cycling_transform(h):
    h = np.clip(np.asarray(h, dtype=float), 0, 1)
    return (h + KAPPA * np.maximum(h - TAU, 0) ** 2) / (1 + KAPPA * (1 - TAU) ** 2)


def test_metrics(frame, target, hrr_column="hrr", unit="file", quantized=False):
    h = np.clip(frame[hrr_column].to_numpy(dtype=float), 0, 1)
    if quantized:
        h = np.minimum(np.floor(h * 10) / 10 + 0.05, 0.95)
    y = frame[target].to_numpy(dtype=float)
    temp = frame[[unit]].copy()
    temp["linear_abs_error"] = np.abs(h - y)
    temp["cycling_abs_error"] = np.abs(cycling_transform(h) - y)
    temp["linear_sq_error"] = (h - y) ** 2
    temp["cycling_sq_error"] = (cycling_transform(h) - y) ** 2
    temp["linear_bias"] = h - y
    temp["cycling_bias"] = cycling_transform(h) - y
    return temp.groupby(unit, sort=False).mean(numeric_only=True).reset_index()


def paired_bootstrap(per_unit, n_boot=10000):
    delta = per_unit["cycling_abs_error"].to_numpy() - per_unit["linear_abs_error"].to_numpy()
    rng = np.random.default_rng(SEED)
    indices = rng.integers(0, len(delta), size=(n_boot, len(delta)))
    samples = delta[indices].mean(axis=1)
    return {
        "delta_mae": float(delta.mean()),
        "ci_low": float(np.quantile(samples, 0.025)),
        "ci_high": float(np.quantile(samples, 0.975)),
        "win_count": int(np.sum(delta < 0)),
        "tie_count": int(np.sum(delta == 0)),
        "n_units": int(len(delta)),
    }


def bootstrap_difference(first, second, n_boot=10000):
    """Cluster bootstrap of first-model MAE minus second-model MAE."""
    delta = np.asarray(first, dtype=float) - np.asarray(second, dtype=float)
    rng = np.random.default_rng(SEED)
    indices = rng.integers(0, len(delta), size=(n_boot, len(delta)))
    samples = delta[indices].mean(axis=1)
    return float(delta.mean()), float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975))


def fit_linear_comparators(frame, target, quantized=False):
    h = np.clip(frame["hrr"].to_numpy(dtype=float), 0, 1)
    if quantized:
        h = np.minimum(np.floor(h * 10) / 10 + 0.05, 0.95)
    y = frame[target].to_numpy(dtype=float)
    weights = 1.0 / frame.groupby("file")["file"].transform("size").to_numpy(dtype=float)
    scale = float(np.sum(weights * h * y) / np.sum(weights * h * h))
    design = np.column_stack([np.ones(len(h)), h])
    root_w = np.sqrt(weights)
    intercept, slope = np.linalg.lstsq(design * root_w[:, None], y * root_w, rcond=None)[0]
    return {"scale": scale, "intercept": float(intercept), "slope": float(slope)}


def strong_comparator_metrics(frame, target, unit, parameters, quantized=False):
    h = np.clip(frame["hrr"].to_numpy(dtype=float), 0, 1)
    if quantized:
        h = np.minimum(np.floor(h * 10) / 10 + 0.05, 0.95)
    y = frame[target].to_numpy(dtype=float)
    predictions = {
        "raw_linear": h,
        "scaled_linear": np.clip(parameters["scale"] * h, 0, 1),
        "affine_linear": np.clip(parameters["intercept"] + parameters["slope"] * h, 0, 1),
        "cycling_tail": cycling_transform(h),
    }
    work = frame[[unit]].copy()
    for name, prediction in predictions.items():
        work[name] = np.abs(prediction - y)
    return work.groupby(unit, sort=False).mean(numeric_only=True).reset_index()


def sign_flip_p(per_unit, n_perm=100000):
    delta = per_unit["cycling_abs_error"].to_numpy() - per_unit["linear_abs_error"].to_numpy()
    observed = abs(delta.mean())
    rng = np.random.default_rng(SEED + 1)
    extreme = 0
    done = 0
    batch = 5000
    while done < n_perm:
        size = min(batch, n_perm - done)
        signs = rng.choice([-1.0, 1.0], size=(size, len(delta)))
        permuted = np.abs((signs * delta).mean(axis=1))
        extreme += int(np.sum(permuted >= observed))
        done += size
    return (extreme + 1) / (n_perm + 1)


def weighted_calibration(frame, target, prediction, unit="file"):
    work = frame[[unit, target]].copy()
    work["prediction"] = prediction
    counts = work.groupby(unit)[unit].transform("size").to_numpy(dtype=float)
    weights = 1.0 / counts
    x = work["prediction"].to_numpy(dtype=float)
    y = work[target].to_numpy(dtype=float)
    design = np.column_stack([np.ones(len(x)), x])
    root_w = np.sqrt(weights)
    beta = np.linalg.lstsq(design * root_w[:, None], y * root_w, rcond=None)[0]
    residual = y - design @ beta
    y_mean = np.average(y, weights=weights)
    r2 = 1 - np.sum(weights * residual**2) / np.sum(weights * (y - y_mean) ** 2)
    return {"intercept": float(beta[0]), "slope": float(beta[1]), "calibration_r2": float(r2)}


def summarize(per_unit, frame, target, dataset, unit, quantized=False):
    boot = paired_bootstrap(per_unit)
    h = np.clip(frame["hrr"].to_numpy(dtype=float), 0, 1)
    if quantized:
        h = np.minimum(np.floor(h * 10) / 10 + 0.05, 0.95)
    linear_cal = weighted_calibration(frame, target, h, unit)
    cycling_cal = weighted_calibration(frame, target, cycling_transform(h), unit)
    return {
        "dataset": dataset,
        "target": target,
        "representation": "10-bin midpoint" if quantized else "continuous",
        "n_analysis_units": len(per_unit),
        "linear_mae": float(per_unit["linear_abs_error"].mean()),
        "cycling_mae": float(per_unit["cycling_abs_error"].mean()),
        "delta_mae_cycling_minus_linear": boot["delta_mae"],
        "delta_mae_ci_low": boot["ci_low"],
        "delta_mae_ci_high": boot["ci_high"],
        "relative_mae_change_percent": float(100 * boot["delta_mae"] / per_unit["linear_abs_error"].mean()),
        "linear_rmse": float(np.sqrt(per_unit["linear_sq_error"].mean())),
        "cycling_rmse": float(np.sqrt(per_unit["cycling_sq_error"].mean())),
        "linear_mean_bias": float(per_unit["linear_bias"].mean()),
        "cycling_mean_bias": float(per_unit["cycling_bias"].mean()),
        "cycling_wins": boot["win_count"],
        "ties": boot["tie_count"],
        "two_sided_sign_flip_p": sign_flip_p(per_unit),
        "linear_calibration_intercept": linear_cal["intercept"],
        "linear_calibration_slope": linear_cal["slope"],
        "linear_calibration_r2": linear_cal["calibration_r2"],
        "cycling_calibration_intercept": cycling_cal["intercept"],
        "cycling_calibration_slope": cycling_cal["slope"],
        "cycling_calibration_r2": cycling_cal["calibration_r2"],
    }


def prepare_actes(path):
    data = pd.read_csv(path)
    data["hr"] = 60000 / data["RR"]
    frames = []
    audit = []
    for participant, group in data.groupby("ID"):
        baseline = group.loc[(group["time"] < 0) & (group["power"] == 0)]
        hr0 = float(baseline["hr"].median())
        vo20 = float(baseline["VO2"].median())
        active = group.loc[group["time"] >= 0].copy()
        active["time_bin"] = np.floor(active["time"] / 10).astype(int)
        active = active.groupby("time_bin", as_index=False).agg(
            hr=("hr", "median"), vo2=("VO2", "median"), power=("power", "median")
        )
        hrmax = float(active["hr"].max())
        vo2max = float(active["vo2"].max())
        powermax = float(active["power"].max())
        active = active.loc[active["power"] > 0].copy()
        active["ID"] = participant
        active["hrr"] = (active["hr"] - hr0) / (hrmax - hr0)
        active["vo2r"] = (active["vo2"] - vo20) / (vo2max - vo20)
        active["power_fraction"] = active["power"] / powermax
        active = active.loc[active["hrr"].between(-0.10, 1.10) & active["vo2r"].between(-0.10, 1.10)]
        frames.append(active)
        audit.append({
            "ID": participant, "n_10s_active_bins": len(active), "baseline_hr": hr0,
            "hrmax": hrmax, "baseline_vo2": vo20, "vo2max": vo2max,
            "powermax": powermax,
        })
    return pd.concat(frames, ignore_index=True), pd.DataFrame(audit)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--graded", type=Path, required=True)
    parser.add_argument("--splits", type=Path, required=True)
    parser.add_argument("--actes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    graded = pd.read_csv(args.graded, parse_dates=["test_date"])
    splits = pd.read_csv(args.splits)
    graded = graded.merge(splits[["file", "split"]], on="file", how="left")
    holdout = graded.loc[(graded["sport"] == "Cycling") & (graded["split"] == "holdout")].copy()
    development = graded.loc[(graded["sport"] == "Cycling") & (graded["split"] == "development")].copy()

    summaries = []
    per_unit_outputs = []
    for target in ["vo2r", "load_fraction"]:
        for quantized in [False, True]:
            per_test = test_metrics(holdout, target, unit="file", quantized=quantized)
            per_test["dataset"] = "Graded-test temporal holdout"
            per_test["target"] = target
            per_test["representation"] = "10-bin midpoint" if quantized else "continuous"
            per_unit_outputs.append(per_test)
            summaries.append(summarize(per_test, holdout, target, "Graded-test temporal holdout", "file", quantized))

    actes, actes_audit = prepare_actes(args.actes)
    actes.to_csv(args.output / "actes_processed_10s.csv", index=False)
    actes_audit.to_csv(args.output / "actes_processing_audit.csv", index=False)
    for target in ["vo2r", "power_fraction"]:
        for quantized in [False, True]:
            per_id = test_metrics(actes, target, unit="ID", quantized=quantized)
            per_id["dataset"] = "ACTES external validation"
            per_id["target"] = target
            per_id["representation"] = "10-bin midpoint" if quantized else "continuous"
            per_unit_outputs.append(per_id)
            summaries.append(summarize(per_id, actes, target, "ACTES external validation", "ID", quantized))

    summary = pd.DataFrame(summaries)
    summary.to_csv(args.output / "locked_validation_summary.csv", index=False)
    pd.concat(per_unit_outputs, ignore_index=True).to_csv(args.output / "locked_validation_per_unit.csv", index=False)

    # Strong-comparator audit. Linear scaling and affine calibration are fitted
    # only in the cycling development data and then transferred unchanged to the
    # temporal holdout and ACTES external dataset.
    comparator_rows = []
    comparator_per_unit = []
    linear_parameters = []
    for representation_quantized in [False, True]:
        representation = "10-bin midpoint" if representation_quantized else "continuous"
        parameters_by_target = {}
        for development_target in ["vo2r", "load_fraction"]:
            parameters = fit_linear_comparators(development, development_target, representation_quantized)
            parameters_by_target[development_target] = parameters
            linear_parameters.append({"target": development_target, "representation": representation, **parameters})
        validation_sets = [
            ("Graded-test temporal holdout", holdout, "vo2r", "vo2r", "file"),
            ("Graded-test temporal holdout", holdout, "load_fraction", "load_fraction", "file"),
            ("ACTES external validation", actes, "vo2r", "vo2r", "ID"),
            ("ACTES external validation", actes, "power_fraction", "load_fraction", "ID"),
        ]
        for dataset_name, frame, target, parameter_target, unit in validation_sets:
            metrics = strong_comparator_metrics(
                frame, target, unit, parameters_by_target[parameter_target], representation_quantized
            )
            metrics["dataset"] = dataset_name
            metrics["target"] = target
            metrics["representation"] = representation
            comparator_per_unit.append(metrics)
            for comparator in ["raw_linear", "scaled_linear", "affine_linear"]:
                delta, low, high = bootstrap_difference(metrics["cycling_tail"], metrics[comparator])
                comparator_rows.append({
                    "dataset": dataset_name,
                    "target": target,
                    "representation": representation,
                    "n_analysis_units": len(metrics),
                    "comparator": comparator,
                    "comparator_mae": metrics[comparator].mean(),
                    "cycling_tail_mae": metrics["cycling_tail"].mean(),
                    "delta_mae_tail_minus_comparator": delta,
                    "delta_ci_low": low,
                    "delta_ci_high": high,
                    "tail_wins": int(np.sum(metrics["cycling_tail"] < metrics[comparator])),
                })
    pd.DataFrame(linear_parameters).to_csv(args.output / "development_linear_comparator_parameters.csv", index=False)
    pd.DataFrame(comparator_rows).to_csv(args.output / "strong_comparator_summary.csv", index=False)
    pd.concat(comparator_per_unit, ignore_index=True).to_csv(args.output / "strong_comparator_per_unit.csv", index=False)

    # Anchor sensitivity in the temporal holdout; the physiological target is
    # unchanged while HR resting/max anchors are perturbed by plausible amounts.
    sensitivity = []
    for resting_shift in [-5, 0, 5]:
        for max_shift in [-5, 0, 5]:
            varied = holdout.copy()
            varied["hrr_varied"] = (
                varied["hr"] - (varied["baseline_hr"] + resting_shift)
            ) / (
                (varied["hrmax"] + max_shift) - (varied["baseline_hr"] + resting_shift)
            )
            per_test = test_metrics(varied, "vo2r", hrr_column="hrr_varied", unit="file")
            sensitivity.append({
                "resting_hr_shift_bpm": resting_shift,
                "max_hr_shift_bpm": max_shift,
                "linear_mae": per_test["linear_abs_error"].mean(),
                "cycling_mae": per_test["cycling_abs_error"].mean(),
                "delta_mae": (per_test["cycling_abs_error"] - per_test["linear_abs_error"]).mean(),
            })
    pd.DataFrame(sensitivity).to_csv(args.output / "anchor_sensitivity.csv", index=False)

    locked = {
        "sport": "Cycling",
        "model_family": "normalized quadratic tail transform",
        "tau": TAU,
        "kappa": KAPPA,
        "denominator": 1 + KAPPA * (1 - TAU) ** 2,
        "selection_source": "development-only grouped cross-validation",
        "primary_target": "VO2 reserve",
        "primary_validation_unit": "complete graded test",
        "external_validation_unit": "ACTES participant",
    }
    (args.output / "locked_model.json").write_text(json.dumps(locked, indent=2), encoding="utf-8")
    print(summary[[
        "dataset", "target", "representation", "n_analysis_units", "linear_mae",
        "cycling_mae", "delta_mae_cycling_minus_linear", "delta_mae_ci_low",
        "delta_mae_ci_high", "relative_mae_change_percent", "cycling_wins",
        "two_sided_sign_flip_p",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()
