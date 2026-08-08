#!/usr/bin/env python3
"""Reviewer-requested robustness and practical-interpretation analyses.

All analyses use the locked CycHRR-T parameters. They do not update the model.
Complete graded tests and ACTES participants remain the resampling units.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


TAU = 0.90
KAPPA = 5.75
SEED = 20260808
N_BOOT = 10_000


def transform(h, tau=TAU, kappa=KAPPA):
    h = np.clip(np.asarray(h, dtype=float), 0, 1)
    return (h + kappa * np.maximum(h - tau, 0) ** 2) / (1 + kappa * (1 - tau) ** 2)


def bootstrap_delta(values, seed_offset=0):
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(SEED + seed_offset)
    indices = rng.integers(0, len(values), size=(N_BOOT, len(values)))
    means = values[indices].mean(axis=1)
    return float(values.mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def predictions(frame, parameters):
    h = np.clip(frame["hrr"].to_numpy(dtype=float), 0, 1)
    return {
        "raw_hrr": h,
        "scaled_linear": np.clip(parameters["scale"] * h, 0, 1),
        "affine_linear": np.clip(parameters["intercept"] + parameters["slope"] * h, 0, 1),
        "cychrr_t": transform(h),
    }


def per_unit_errors(frame, target, unit, parameters):
    work = frame[[unit]].copy()
    y = np.clip(frame[target].to_numpy(dtype=float), 0, 1)
    for name, pred in predictions(frame, parameters).items():
        work[name] = np.abs(pred - y)
    return work.groupby(unit, sort=False).mean(numeric_only=True).reset_index()


def endpoint_exclusion(validation_sets, params_by_target, out):
    all_units = []
    rows = []
    for dataset, frame, target, parameter_target, unit in validation_sets:
        scenarios = {
            "all observations": frame.copy(),
            "exclude each unit target maximum": frame.loc[
                frame[target] < frame.groupby(unit)[target].transform("max") - 1e-12
            ].copy(),
            "exclude HRR >= 0.95": frame.loc[frame["hrr"] < 0.95].copy(),
        }
        for scenario, subset in scenarios.items():
            metrics = per_unit_errors(subset, target, unit, params_by_target[parameter_target])
            metrics["dataset"] = dataset
            metrics["target"] = target
            metrics["scenario"] = scenario
            all_units.append(metrics)
            for comparator in ["raw_hrr", "scaled_linear", "affine_linear"]:
                delta, low, high = bootstrap_delta(metrics["cychrr_t"] - metrics[comparator], len(rows))
                rows.append({
                    "dataset": dataset,
                    "target": target,
                    "scenario": scenario,
                    "n_complete_units": len(metrics),
                    "n_observations": len(subset),
                    "comparator": comparator,
                    "comparator_mae": metrics[comparator].mean(),
                    "cychrr_t_mae": metrics["cychrr_t"].mean(),
                    "delta_mae_tail_minus_comparator": delta,
                    "delta_ci_low": low,
                    "delta_ci_high": high,
                    "absolute_difference_percentage_points": 100 * delta,
                    "cychrr_t_wins": int((metrics["cychrr_t"] < metrics[comparator]).sum()),
                })
    pd.DataFrame(rows).to_csv(out / "endpoint_exclusion_summary.csv", index=False)
    pd.concat(all_units, ignore_index=True).to_csv(out / "endpoint_exclusion_per_unit.csv", index=False)


def intensity_bands(validation_sets, params_by_target, out):
    edges = [-np.inf, 0.60, 0.80, 0.90, np.inf]
    labels = ["<0.60", "0.60-<0.80", "0.80-<0.90", ">=0.90"]
    rows = []
    unit_rows = []
    for dataset, frame, target, parameter_target, unit in validation_sets:
        labelled = frame.copy()
        labelled["hrr_band"] = pd.cut(labelled["hrr"], bins=edges, labels=labels, right=False)
        for band in labels:
            subset = labelled.loc[labelled["hrr_band"] == band].copy()
            if subset.empty:
                continue
            metrics = per_unit_errors(subset, target, unit, params_by_target[parameter_target])
            metrics["dataset"] = dataset
            metrics["target"] = target
            metrics["hrr_band"] = band
            unit_rows.append(metrics)
            for comparator in ["raw_hrr", "scaled_linear", "affine_linear"]:
                delta, low, high = bootstrap_delta(metrics["cychrr_t"] - metrics[comparator], len(rows) + 100)
                rows.append({
                    "dataset": dataset,
                    "target": target,
                    "hrr_band": band,
                    "n_complete_units_with_data": len(metrics),
                    "n_observations": len(subset),
                    "comparator": comparator,
                    "comparator_mae": metrics[comparator].mean(),
                    "cychrr_t_mae": metrics["cychrr_t"].mean(),
                    "delta_mae_tail_minus_comparator": delta,
                    "delta_ci_low": low,
                    "delta_ci_high": high,
                    "absolute_difference_percentage_points": 100 * delta,
                })
    pd.DataFrame(rows).to_csv(out / "intensity_band_summary.csv", index=False)
    pd.concat(unit_rows, ignore_index=True).to_csv(out / "intensity_band_per_unit.csv", index=False)


def ten_percent_bin_agreement(validation_sets, params_by_target, out):
    summary_rows = []
    comparison_rows = []
    per_unit_rows = []
    for dataset, frame, target, parameter_target, unit in validation_sets:
        y = np.clip(frame[target].to_numpy(dtype=float), 0, 1)
        target_bin = np.minimum((y * 10).astype(int), 9)
        work = frame[[unit]].copy()
        for model, pred in predictions(frame, params_by_target[parameter_target]).items():
            pred_bin = np.minimum((np.clip(pred, 0, 1) * 10).astype(int), 9)
            difference = np.abs(pred_bin - target_bin)
            work[f"{model}_exact"] = (difference == 0).astype(float)
            work[f"{model}_within_one"] = (difference <= 1).astype(float)
            work[f"{model}_bin_error"] = difference.astype(float)
        per_unit = work.groupby(unit, sort=False).mean(numeric_only=True).reset_index()
        per_unit["dataset"] = dataset
        per_unit["target"] = target
        per_unit_rows.append(per_unit)
        for model in ["raw_hrr", "scaled_linear", "affine_linear", "cychrr_t"]:
            summary_rows.append({
                "dataset": dataset,
                "target": target,
                "n_complete_units": len(per_unit),
                "n_observations": len(frame),
                "model": model,
                "exact_10pct_bin_agreement": per_unit[f"{model}_exact"].mean(),
                "within_one_10pct_bin_agreement": per_unit[f"{model}_within_one"].mean(),
                "mean_absolute_bin_error": per_unit[f"{model}_bin_error"].mean(),
            })
        for comparator in ["raw_hrr", "scaled_linear", "affine_linear"]:
            for metric, direction in [("exact", "higher_is_better"), ("within_one", "higher_is_better"),
                                      ("bin_error", "lower_is_better")]:
                delta_values = per_unit[f"cychrr_t_{metric}"] - per_unit[f"{comparator}_{metric}"]
                delta, low, high = bootstrap_delta(delta_values, len(comparison_rows) + 300)
                comparison_rows.append({
                    "dataset": dataset,
                    "target": target,
                    "n_complete_units": len(per_unit),
                    "metric": metric,
                    "direction": direction,
                    "comparator": comparator,
                    "delta_cychrr_t_minus_comparator": delta,
                    "delta_ci_low": low,
                    "delta_ci_high": high,
                })
    pd.DataFrame(summary_rows).to_csv(out / "ten_percent_bin_agreement_summary.csv", index=False)
    pd.DataFrame(comparison_rows).to_csv(out / "ten_percent_bin_agreement_comparisons.csv", index=False)
    pd.concat(per_unit_rows, ignore_index=True).to_csv(out / "ten_percent_bin_agreement_per_unit.csv", index=False)


def actes_lag_sensitivity(actes, params_by_target, out):
    rows = []
    for offset_seconds in [-30, -20, -10, 0, 10, 20, 30]:
        shifted = actes.copy().sort_values(["ID", "time_bin"])
        # Positive values compare a later HR-derived estimate with the current
        # criterion value, a simple correction for delayed HR kinetics.
        bins = offset_seconds // 10
        shifted["hrr_original"] = shifted["hrr"]
        shifted["hrr"] = shifted.groupby("ID")["hrr_original"].shift(-bins)
        shifted = shifted.dropna(subset=["hrr"]).copy()
        for target, parameter_target in [("vo2r", "vo2r"), ("power_fraction", "load_fraction")]:
            metrics = per_unit_errors(shifted, target, "ID", params_by_target[parameter_target])
            rows.append({
                "hr_alignment_offset_seconds": offset_seconds,
                "target": target,
                "n_participants": len(metrics),
                "n_aligned_bins": len(shifted),
                "raw_hrr_mae": metrics["raw_hrr"].mean(),
                "scaled_linear_mae": metrics["scaled_linear"].mean(),
                "affine_linear_mae": metrics["affine_linear"].mean(),
                "cychrr_t_mae": metrics["cychrr_t"].mean(),
                "delta_tail_minus_raw": (metrics["cychrr_t"] - metrics["raw_hrr"]).mean(),
                "delta_tail_minus_scaled": (metrics["cychrr_t"] - metrics["scaled_linear"]).mean(),
            })
    pd.DataFrame(rows).to_csv(out / "actes_lag_sensitivity.csv", index=False)


def parameter_sensitivity(validation_sets, out):
    candidates = [(0.85, 3.0), (0.85, 5.75), (0.90, 3.0), (0.90, 5.75),
                  (0.90, 8.0), (0.90, 12.0), (0.95, 10.0), (0.95, 20.0)]
    rows = []
    for dataset, frame, target, _, unit in validation_sets:
        h = np.clip(frame["hrr"].to_numpy(dtype=float), 0, 1)
        y = np.clip(frame[target].to_numpy(dtype=float), 0, 1)
        for tau, kappa in candidates:
            work = frame[[unit]].copy()
            work["absolute_error"] = np.abs(transform(h, tau, kappa) - y)
            per_unit = work.groupby(unit, sort=False)["absolute_error"].mean()
            rows.append({
                "dataset": dataset,
                "target": target,
                "tau": tau,
                "kappa": kappa,
                "locked_parameters": tau == TAU and kappa == KAPPA,
                "n_complete_units": len(per_unit),
                "mae": per_unit.mean(),
            })
    pd.DataFrame(rows).to_csv(out / "parameter_sensitivity.csv", index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--graded", type=Path, required=True)
    parser.add_argument("--splits", type=Path, required=True)
    parser.add_argument("--actes-processed", type=Path, required=True)
    parser.add_argument("--linear-parameters", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    graded = pd.read_csv(args.graded)
    splits = pd.read_csv(args.splits)
    graded = graded.merge(splits[["file", "split"]], on="file", how="left")
    holdout = graded.loc[(graded["sport"] == "Cycling") & (graded["split"] == "holdout")].copy()
    actes = pd.read_csv(args.actes_processed)
    parameter_table = pd.read_csv(args.linear_parameters)
    params_by_target = {
        target: parameter_table.loc[
            (parameter_table["target"] == target) & (parameter_table["representation"] == "continuous")
        ].iloc[0].to_dict()
        for target in ["vo2r", "load_fraction"]
    }
    validation_sets = [
        ("Graded-test temporal holdout", holdout, "vo2r", "vo2r", "file"),
        ("Graded-test temporal holdout", holdout, "load_fraction", "load_fraction", "file"),
        ("ACTES external validation", actes, "vo2r", "vo2r", "ID"),
        ("ACTES external validation", actes, "power_fraction", "load_fraction", "ID"),
    ]
    endpoint_exclusion(validation_sets, params_by_target, args.output)
    intensity_bands(validation_sets, params_by_target, args.output)
    ten_percent_bin_agreement(validation_sets, params_by_target, args.output)
    actes_lag_sensitivity(actes, params_by_target, args.output)
    parameter_sensitivity(validation_sets, args.output)
    print("Reviewer-requested analyses written to", args.output)


if __name__ == "__main__":
    main()
