from __future__ import annotations

"""Reviewer-round-5 analyses.

This module addresses the central incremental-validity question without selecting
models by result direction.  The candidate set is deliberately small and
interpretable.  All feature and parameter selection occurs inside participant-
grouped cross-validation, and the outer leave-one-participant-out (LOPO) folds
remain untouched until final evaluation.
"""

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
ANALYSIS = ROOT / "analysis"
RANDOM_SEED = 20260801
BOOTSTRAP_REPLICATES = 5000
CENTERS = (np.arange(1, 11, dtype=float) - 0.5) / 10.0
LAMBDA_GRID = np.round(np.arange(0.0, 15.01, 0.1), 1)


def add_distribution_features(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    proportions = output[[f"p{i}" for i in range(1, 11)]].to_numpy(dtype=float)
    mean = proportions @ CENTERS
    variance = np.sum(proportions * (CENTERS[None, :] - mean[:, None]) ** 2, axis=1)
    output["mean_hrr_binned"] = mean
    output["hrr_variance"] = variance
    output["hrr_sd"] = np.sqrt(np.maximum(variance, 0.0))
    output["time_hrr_ge_70"] = proportions[:, 7:].sum(axis=1)
    output["time_hrr_ge_80"] = proportions[:, 8:].sum(axis=1)
    output["time_hrr_ge_90"] = proportions[:, 9]
    output["upper_tail_area_70"] = proportions @ np.maximum(CENTERS - 0.70, 0.0)
    return output


def tilted_hrr(frame: pd.DataFrame, lam: float) -> np.ndarray:
    proportions = frame[[f"p{i}" for i in range(1, 11)]].to_numpy(dtype=float)
    weights = np.exp(float(lam) * CENTERS)
    return (proportions @ (CENTERS * weights)) / (proportions @ weights)


def participant_weights(participant: np.ndarray) -> np.ndarray:
    values = pd.Series(participant.astype(str))
    counts = values.value_counts()
    return values.map(lambda value: 1.0 / counts[value]).to_numpy(dtype=float)


def fit_weighted_linear(x: np.ndarray, y: np.ndarray, participant: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    design = np.column_stack([np.ones(len(x)), x])
    weight = participant_weights(np.asarray(participant))
    root_weight = np.sqrt(weight)
    coefficient, *_ = np.linalg.lstsq(
        design * root_weight[:, None], y.astype(float) * root_weight, rcond=None
    )
    return coefficient


def predict_linear(coefficient: np.ndarray, x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    return np.column_stack([np.ones(len(x)), x]) @ coefficient


def participant_balanced_mae(frame: pd.DataFrame, prediction: str) -> float:
    values = frame.groupby("participant", sort=True).apply(
        lambda group: float(np.mean(np.abs(group[prediction] - group["rpe"]))),
        include_groups=False,
    )
    return float(values.mean())


def feature_matrix(frame: pd.DataFrame, family: str, parameter: float | None) -> np.ndarray:
    mean = frame["mean_hrr_binned"].to_numpy(dtype=float)
    if family == "base_mean":
        return mean[:, None]
    if family == "delta_tilt":
        if parameter is None:
            raise ValueError("delta_tilt requires lambda")
        delta = tilted_hrr(frame, parameter) - mean
        return np.column_stack([mean, delta])
    if family == "tilted_standalone":
        if parameter is None:
            raise ValueError("tilted_standalone requires lambda")
        return tilted_hrr(frame, parameter)[:, None]
    if family == "variance":
        return frame[["mean_hrr_binned", "hrr_variance"]].to_numpy(dtype=float)
    if family == "upper_70":
        return frame[["mean_hrr_binned", "time_hrr_ge_70"]].to_numpy(dtype=float)
    if family == "upper_80":
        return frame[["mean_hrr_binned", "time_hrr_ge_80"]].to_numpy(dtype=float)
    if family == "upper_90":
        return frame[["mean_hrr_binned", "time_hrr_ge_90"]].to_numpy(dtype=float)
    if family == "upper_tail_area_70":
        return frame[["mean_hrr_binned", "upper_tail_area_70"]].to_numpy(dtype=float)
    raise KeyError(family)


def inner_lopo_predictions(frame: pd.DataFrame, family: str, parameter: float | None) -> pd.DataFrame:
    outputs = []
    for held_out in sorted(frame["participant"].astype(str).unique()):
        train = frame[frame["participant"].astype(str) != held_out]
        test = frame[frame["participant"].astype(str) == held_out]
        coefficient = fit_weighted_linear(
            feature_matrix(train, family, parameter),
            train["rpe"].to_numpy(dtype=float),
            train["participant"].to_numpy(),
        )
        fold = test[["participant", "rpe"]].copy()
        fold["prediction"] = predict_linear(coefficient, feature_matrix(test, family, parameter))
        outputs.append(fold)
    return pd.concat(outputs, ignore_index=True)


def select_candidate(frame: pd.DataFrame, include_family_selection: bool) -> tuple[str, float | None, pd.DataFrame]:
    candidates: list[tuple[str, float | None]] = [
        ("delta_tilt", float(lam)) for lam in LAMBDA_GRID
    ]
    if include_family_selection:
        candidates.extend([
            ("base_mean", None),
            ("variance", None),
            ("upper_70", None),
            ("upper_80", None),
            ("upper_90", None),
            ("upper_tail_area_70", None),
        ])
    rows = []
    for order, (family, parameter) in enumerate(candidates):
        predictions = inner_lopo_predictions(frame, family, parameter)
        rows.append({
            "family": family,
            "parameter": parameter,
            "candidate_order": order,
            "inner_participant_balanced_mae": participant_balanced_mae(predictions, "prediction"),
        })
    profile = pd.DataFrame(rows)
    best = profile.sort_values(
        ["inner_participant_balanced_mae", "candidate_order"], kind="stable"
    ).iloc[0]
    parameter = None if pd.isna(best["parameter"]) else float(best["parameter"])
    return str(best["family"]), parameter, profile


def outer_lopo(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    output = []
    selections = []
    profiles = []
    fixed_families = ["base_mean", "variance", "upper_70", "upper_80", "upper_90", "upper_tail_area_70"]
    for held_out in sorted(frame["participant"].astype(str).unique()):
        train = frame[frame["participant"].astype(str) != held_out].copy()
        test = frame[frame["participant"].astype(str) == held_out].copy()

        _, selected_lambda, lambda_profile = select_candidate(train, include_family_selection=False)
        selected_family, selected_parameter, family_profile = select_candidate(train, include_family_selection=True)
        lambda_profile["held_out_participant"] = held_out
        lambda_profile["selection_scope"] = "lambda_only"
        family_profile["held_out_participant"] = held_out
        family_profile["selection_scope"] = "family_and_parameter"
        profiles.extend([lambda_profile, family_profile])

        fold = test[["participant", "session_number", "rpe"]].copy()
        evaluated = [(family, None) for family in fixed_families]
        evaluated.extend([
            ("delta_tilt", 6.2),
            ("tilted_standalone", 6.2),
            ("delta_tilt", selected_lambda),
            ("tilted_standalone", selected_lambda),
            (selected_family, selected_parameter),
        ])
        labels = fixed_families + [
            "delta_tilt_fixed_6_2", "tilted_standalone_fixed_6_2",
            "delta_tilt", "tilted_standalone", "selected_transparent",
        ]
        for label, (family, parameter) in zip(labels, evaluated):
            coefficient = fit_weighted_linear(
                feature_matrix(train, family, parameter),
                train["rpe"].to_numpy(dtype=float),
                train["participant"].to_numpy(),
            )
            fold[f"pred_{label}"] = predict_linear(
                coefficient, feature_matrix(test, family, parameter)
            )
        fold["selected_lambda"] = selected_lambda
        fold["selected_transparent_family"] = selected_family
        fold["selected_transparent_parameter"] = selected_parameter
        output.append(fold)
        selections.append({
            "held_out_participant": held_out,
            "training_sessions": len(train),
            "test_sessions": len(test),
            "mae_selected_lambda": selected_lambda,
            "selected_transparent_family": selected_family,
            "selected_transparent_parameter": selected_parameter,
        })
    return pd.concat(output, ignore_index=True), pd.DataFrame(selections), pd.concat(profiles, ignore_index=True)


def exact_sign_flip_p(difference: np.ndarray) -> float:
    difference = np.asarray(difference, dtype=float)
    observed = abs(float(difference.mean()))
    extreme = 0
    total = 0
    for signs in itertools.product((-1.0, 1.0), repeat=len(difference)):
        statistic = abs(float(np.mean(difference * np.asarray(signs))))
        extreme += statistic >= observed - 1e-15
        total += 1
    return float(extreme / total)


def summarize_predictions(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(RANDOM_SEED)
    models = [column.removeprefix("pred_") for column in predictions if column.startswith("pred_")]
    participants = sorted(predictions["participant"].astype(str).unique())
    participant_rows = []
    for participant in participants:
        group = predictions[predictions["participant"].astype(str) == participant]
        row = {"participant": participant, "sessions": len(group)}
        for model in models:
            error = group[f"pred_{model}"].to_numpy(dtype=float) - group["rpe"].to_numpy(dtype=float)
            row[f"mae_{model}"] = float(np.mean(np.abs(error)))
            row[f"rmse_{model}"] = float(np.sqrt(np.mean(error**2)))
        participant_rows.append(row)
    participant_table = pd.DataFrame(participant_rows)
    base = participant_table["mae_base_mean"].to_numpy(dtype=float)
    summary_rows = []
    for model in models:
        values = participant_table[f"mae_{model}"].to_numpy(dtype=float)
        difference = values - base
        boot = np.asarray([
            rng.choice(difference, len(difference), replace=True).mean()
            for _ in range(BOOTSTRAP_REPLICATES)
        ])
        jackknife = np.asarray([
            np.delete(difference, index).mean() for index in range(len(difference))
        ])
        summary_rows.append({
            "model": model,
            "participants": len(values),
            "participant_balanced_mae": float(values.mean()),
            "mae_difference_vs_base": float(difference.mean()),
            "relative_mae_change_percent": float(100.0 * difference.mean() / base.mean()),
            "bootstrap_ci_low": float(np.percentile(boot, 2.5)),
            "bootstrap_ci_high": float(np.percentile(boot, 97.5)),
            "exact_two_sided_sign_flip_p": exact_sign_flip_p(difference) if model != "base_mean" else np.nan,
            "participants_favoring_model": int((difference < 0).sum()),
            "participants_favoring_base": int((difference > 0).sum()),
            "leave_one_participant_out_difference_min": float(jackknife.min()),
            "leave_one_participant_out_difference_max": float(jackknife.max()),
        })
    return pd.DataFrame(summary_rows), participant_table


def build_sample_flow_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    primary_flow = pd.DataFrame([
        ("Archived PMSys RPE records", 783, "all archived RPE rows"),
        ("Broad tracker-linked pairs", 469, "timestamp and activity-compatible links"),
        ("Bidirectionally unique broad pairs", 447, "unique in both matching directions"),
        ("Unique broad pairs passing HR quality control", 267, "heart-rate signal criteria satisfied"),
        ("Primary analysis sessions", 255, "all primary matching and outcome criteria satisfied"),
    ], columns=["stage", "sessions", "definition"])
    sensitivity = pd.DataFrame([
        ("Primary 15-180 min", 449, 443, 255, 255),
        ("15-90 min", 401, 398, 225, 232),
        ("30-120 min", 413, 408, 232, 240),
        ("Duration difference <=10 min", 363, 357, 214, 220),
        ("Delay-priority cost", 449, 443, 255, 264),
        ("Duration-priority cost", 449, 443, 255, 264),
    ], columns=[
        "rule", "selected_pairs", "bidirectionally_unique_pairs",
        "original_primary_pairs_retained", "rebuilt_analysis_sessions",
    ])
    sensitivity["interpretation"] = (
        "Retained counts track IDs from the 255-session primary set; rebuilt counts include "
        "newly eligible matches after the rule-specific reconstruction and full quality control."
    )
    return primary_flow, sensitivity


def main() -> None:
    frame = pd.read_csv(ANALYSIS / "pmdata_primary_analysis_sessions.csv")
    frame["participant"] = frame["participant"].astype(str)
    frame = add_distribution_features(frame)

    predictions, selections, profiles = outer_lopo(frame)
    summary, participant_losses = summarize_predictions(predictions)
    primary_flow, sensitivity_flow = build_sample_flow_tables()

    full_family, full_parameter, full_profile = select_candidate(frame, include_family_selection=True)
    _, full_lambda, full_lambda_profile = select_candidate(frame, include_family_selection=False)
    payload = {
        "analysis_label": "reviewer-round-5 prespecified transparent candidate comparison",
        "independent_participants": int(frame["participant"].nunique()),
        "sessions": int(len(frame)),
        "primary_comparison": "mean HRR versus mean HRR plus delta_tilt",
        "primary_selection_objective": "participant-balanced MAE in inner participant-grouped LOPO",
        "full_sample_cross_validated_lambda": full_lambda,
        "full_sample_selected_transparent_family": full_family,
        "full_sample_selected_transparent_parameter": full_parameter,
        "candidate_set": [
            "mean HRR only", "mean HRR + delta_tilt(lambda)", "tilted HRR alone",
            "mean HRR + delta_tilt(lambda=6.2 fixed)", "tilted HRR(lambda=6.2 fixed) alone",
            "mean HRR + variance", "mean HRR + time >=70% HRR",
            "mean HRR + time >=80% HRR", "mean HRR + time >=90% HRR",
            "mean HRR + upper-tail area above 70% HRR",
        ],
        "selection_guardrail": (
            "Candidates were retained regardless of result direction. No model was deleted because "
            "it underperformed. The outer folds were used once for final evaluation."
        ),
        "performance": summary.to_dict("records"),
        "random_seed": RANDOM_SEED,
    }

    predictions.to_csv(ANALYSIS / "reviewer_round5_incremental_predictions.csv", index=False)
    selections.to_csv(ANALYSIS / "reviewer_round5_outer_selections.csv", index=False)
    profiles.to_csv(ANALYSIS / "reviewer_round5_inner_profiles.csv", index=False)
    full_profile.to_csv(ANALYSIS / "reviewer_round5_full_family_profile.csv", index=False)
    full_lambda_profile.to_csv(ANALYSIS / "reviewer_round5_full_lambda_profile.csv", index=False)
    summary.to_csv(ANALYSIS / "reviewer_round5_model_performance.csv", index=False)
    participant_losses.to_csv(ANALYSIS / "reviewer_round5_participant_losses.csv", index=False)
    primary_flow.to_csv(ANALYSIS / "reviewer_round5_primary_sample_flow.csv", index=False)
    sensitivity_flow.to_csv(ANALYSIS / "reviewer_round5_sensitivity_sample_flow.csv", index=False)
    (ANALYSIS / "reviewer_round5_analysis.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
