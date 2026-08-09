#!/usr/bin/env python3
"""Pre-specified development-only comparison of sport-specific HRR transforms.

The latest 30% of tests within each sport are labelled HOLDOUT and are never
used by this script. Model tuning and sport selection use only grouped outer
cross-validation among the earlier 70% of tests.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd


def power_transform(h, gamma):
    return np.clip(h, 0, 1) ** gamma


def exp_transform(h, k):
    h = np.clip(h, 0, 1)
    if abs(k) < 1e-12:
        return h
    return np.expm1(k * h) / np.expm1(k)


def tail_transform(h, tau, kappa):
    h = np.clip(h, 0, 1)
    numerator = h + kappa * np.maximum(h - tau, 0) ** 2
    denominator = 1 + kappa * (1 - tau) ** 2
    return numerator / denominator


def grouped_mean_loss(frame, prediction, target="vo2r", loss="mae"):
    temp = frame[["file", target]].copy()
    error = np.asarray(prediction) - temp[target].to_numpy()
    temp["loss"] = np.abs(error) if loss == "mae" else error**2
    by_test = temp.groupby("file", sort=False)["loss"].mean()
    return float(by_test.mean())


def tune(frame, family, target="vo2r"):
    h = frame["hrr"].to_numpy()
    if family == "linear":
        return {}, grouped_mean_loss(frame, h, target)
    weights = 1.0 / frame.groupby("file")["file"].transform("size").to_numpy(dtype=float)
    y = frame[target].to_numpy(dtype=float)
    if family == "scaled_linear":
        slope = float(np.sum(weights * h * y) / np.sum(weights * h * h))
        prediction = np.clip(slope * h, 0, 1)
        return {"slope": slope}, grouped_mean_loss(frame, prediction, target)
    if family == "affine_linear":
        design = np.column_stack([np.ones(len(h)), h])
        root_w = np.sqrt(weights)
        intercept, slope = np.linalg.lstsq(design * root_w[:, None], y * root_w, rcond=None)[0]
        prediction = np.clip(intercept + slope * h, 0, 1)
        return {"intercept": float(intercept), "slope": float(slope)}, grouped_mean_loss(frame, prediction, target)
    if family == "power":
        candidates = [({"gamma": float(g)}, power_transform(h, g)) for g in np.arange(0.40, 2.501, 0.02)]
    elif family == "exponential":
        candidates = [({"k": float(k)}, exp_transform(h, k)) for k in np.arange(-3.0, 3.001, 0.05)]
    elif family == "tail":
        candidates = []
        for tau in np.arange(0.40, 0.951, 0.05):
            for kappa in np.arange(0, 20.001, 0.25):
                candidates.append(({"tau": float(tau), "kappa": float(kappa)}, tail_transform(h, tau, kappa)))
    else:
        raise ValueError(family)
    scored = [(grouped_mean_loss(frame, prediction, target), params) for params, prediction in candidates]
    score, params = min(scored, key=lambda item: item[0])
    return params, score


def predict(frame, family, params):
    h = frame["hrr"].to_numpy()
    if family == "linear":
        return np.clip(h, 0, 1)
    if family == "scaled_linear":
        return np.clip(params["slope"] * h, 0, 1)
    if family == "affine_linear":
        return np.clip(params["intercept"] + params["slope"] * h, 0, 1)
    if family == "power":
        return power_transform(h, params["gamma"])
    if family == "exponential":
        return exp_transform(h, params["k"])
    if family == "tail":
        return tail_transform(h, params["tau"], params["kappa"])
    raise ValueError(family)


def fold_for_file(file_name, n_folds=5):
    digest = sha256(file_name.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % n_folds


def split_labels(frame):
    labels = []
    for sport, sport_frame in frame.groupby("sport"):
        tests = sport_frame[["file", "test_date"]].drop_duplicates().dropna(subset=["test_date"])
        tests = tests.sort_values(["test_date", "file"])
        cut = int(np.floor(0.70 * len(tests)))
        development = set(tests.iloc[:cut]["file"])
        holdout = set(tests.iloc[cut:]["file"])
        for file_name in sport_frame["file"].unique():
            split = "development" if file_name in development else "holdout" if file_name in holdout else "excluded_missing_date"
            labels.append({"file": file_name, "sport": sport, "split": split})
    return pd.DataFrame(labels)


def metric_rows(validation, prediction, sport, family, target, fold, params):
    temp = validation[["file", target]].copy()
    error = prediction - temp[target].to_numpy()
    temp["absolute_error"] = np.abs(error)
    temp["squared_error"] = error**2
    temp["prediction"] = prediction
    by = temp.groupby("file", sort=False).agg(
        mae=("absolute_error", "mean"),
        mse=("squared_error", "mean"),
        mean_observed=(target, "mean"),
        mean_predicted=("prediction", "mean"),
    ).reset_index()
    return [{
        "sport": sport,
        "family": family,
        "target": target,
        "fold": fold,
        "file": row.file,
        "mae": row.mae,
        "rmse": float(np.sqrt(row.mse)),
        "bias": row.mean_predicted - row.mean_observed,
        "parameters": json.dumps(params, sort_keys=True),
    } for row in by.itertuples()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    data = pd.read_csv(args.input, parse_dates=["test_date"])
    splits = split_labels(data)
    splits.to_csv(args.output / "predefined_test_splits.csv", index=False)
    data = data.merge(splits[["file", "split"]], on="file", how="left")
    development = data.loc[data["split"] == "development"].copy()
    development["fold"] = development["file"].map(fold_for_file)

    families = ["linear", "scaled_linear", "affine_linear", "power", "exponential", "tail"]
    targets = ["vo2r", "load_fraction"]
    rows = []
    for sport, sport_data in development.groupby("sport"):
        for target in targets:
            for fold in range(5):
                training = sport_data.loc[sport_data["fold"] != fold]
                validation = sport_data.loc[sport_data["fold"] == fold]
                for family in families:
                    params, _ = tune(training, family, target)
                    prediction = predict(validation, family, params)
                    rows.extend(metric_rows(validation, prediction, sport, family, target, fold, params))

    metrics = pd.DataFrame(rows)
    metrics.to_csv(args.output / "development_grouped_cv_per_test.csv", index=False)
    summary = metrics.groupby(["sport", "target", "family"]).agg(
        n_tests=("file", "nunique"),
        mae=("mae", "mean"),
        sd_test_mae=("mae", "std"),
        rmse=("rmse", "mean"),
        absolute_bias=("bias", lambda x: np.mean(np.abs(x))),
    ).reset_index()
    linear = summary.loc[summary["family"] == "linear", ["sport", "target", "mae"]].rename(columns={"mae": "linear_mae"})
    summary = summary.merge(linear, on=["sport", "target"])
    summary["delta_mae_vs_linear"] = summary["mae"] - summary["linear_mae"]
    summary["relative_mae_change_percent"] = 100 * summary["delta_mae_vs_linear"] / summary["linear_mae"]
    summary.to_csv(args.output / "development_grouped_cv_summary.csv", index=False)

    # Select a candidate direction without using holdout data. The primary
    # criterion is VO2-reserve MAE improvement, with sample-size and independent
    # external-data availability shown separately rather than hidden in a score.
    vo2 = summary.loc[(summary["target"] == "vo2r") & summary["family"].isin(["power", "exponential", "tail"])].copy()
    best = vo2.sort_values(["sport", "mae"]).groupby("sport", as_index=False).first()
    best["external_dataset_available"] = best["sport"].map({"Cycling": True, "Running": False, "Rowing": False, "Kayak": False})
    best = best.sort_values(["delta_mae_vs_linear", "n_tests"], ascending=[True, False])
    best.to_csv(args.output / "sport_direction_development_comparison.csv", index=False)
    print(best[["sport", "family", "n_tests", "linear_mae", "mae", "delta_mae_vs_linear", "relative_mae_change_percent", "external_dataset_available"]].to_string(index=False))
    print("\nHOLDOUT COUNTS (not analyzed):")
    print(splits.groupby(["sport", "split"]).size().to_string())


if __name__ == "__main__":
    main()
