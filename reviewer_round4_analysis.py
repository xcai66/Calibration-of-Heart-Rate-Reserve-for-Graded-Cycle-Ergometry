from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_whr_as_public_data import fit_weighted_line, predict_weighted_line, spearman_rho
from develop_improved_formula import FAMILIES, score_family, select_parameter
from reviewer_round2_analysis import binned_tilt, select_lambda


ROOT = Path(__file__).resolve().parent
ANALYSIS = ROOT / "analysis"
RANDOM_SEED = 20260731
BOOTSTRAP_REPLICATES = 5000
PERMUTATION_REPLICATES = 5000
MIN_SESSIONS = 5


def participant_mae(frame: pd.DataFrame, prediction: str) -> pd.Series:
    return frame.groupby("participant").apply(
        lambda group: float(np.mean(np.abs(group[prediction] - group["rpe"]))),
        include_groups=False,
    )


def nested_thrr_vs_linear(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    folds = []
    selections = []
    for held_out in sorted(frame["participant"].astype(str).unique()):
        train = frame[frame["participant"].astype(str) != held_out].copy()
        test = frame[frame["participant"].astype(str) == held_out].copy()
        lam = select_lambda(train, "ten_bins")
        train_thrr = binned_tilt(train, 10, lam)
        test_thrr = binned_tilt(test, 10, lam)
        thrr_model = fit_weighted_line(train_thrr, train["rpe"].to_numpy(), train["participant"].to_numpy())
        linear_model = fit_weighted_line(
            train["linear_score"].to_numpy(), train["rpe"].to_numpy(), train["participant"].to_numpy()
        )
        fold = test[["participant", "session_number", "rpe"]].copy()
        fold["score_thrr_i"] = test_thrr
        fold["pred_thrr_i"] = predict_weighted_line(thrr_model, test_thrr)
        fold["pred_linear"] = predict_weighted_line(linear_model, test["linear_score"].to_numpy())
        folds.append(fold)
        selections.append({"held_out_participant": held_out, "selected_lambda": lam})
    return pd.concat(folds, ignore_index=True), pd.DataFrame(selections)


def family_training_objective(frame: pd.DataFrame, family: str, parameter: float) -> float:
    score = score_family(frame, family, parameter)
    working = frame[["participant", "rpe"]].copy()
    working["score"] = score
    values = []
    for _, group in working.groupby("participant"):
        if len(group) < MIN_SESSIONS:
            continue
        rho = spearman_rho(group["score"].to_numpy(), group["rpe"].to_numpy())
        if np.isfinite(rho):
            values.append(rho)
    return float(np.median(values)) if values else float("nan")


def selection_aware_nested(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Outer LOPO evaluation with transformation family and parameter selected only in training data."""
    folds = []
    selections = []
    family_order = list(FAMILIES)
    for held_out in sorted(frame["participant"].astype(str).unique()):
        train = frame[frame["participant"].astype(str) != held_out].copy()
        test = frame[frame["participant"].astype(str) == held_out].copy()
        candidates = []
        for order, family in enumerate(family_order):
            parameter, _ = select_parameter(train, family)
            objective = family_training_objective(train, family, parameter)
            candidates.append((objective, -order, family, parameter))
        objective, _, family, parameter = max(candidates, key=lambda item: (item[0], item[1]))
        train_score = score_family(train, family, parameter)
        test_score = score_family(test, family, parameter)
        selected_model = fit_weighted_line(
            train_score, train["rpe"].to_numpy(), train["participant"].to_numpy()
        )
        linear_model = fit_weighted_line(
            train["linear_score"].to_numpy(), train["rpe"].to_numpy(), train["participant"].to_numpy()
        )
        fold = test[["participant", "session_number", "rpe"]].copy()
        fold["selected_family"] = family
        fold["selected_parameter"] = parameter
        fold["pred_selected_pipeline"] = predict_weighted_line(selected_model, test_score)
        fold["pred_linear"] = predict_weighted_line(linear_model, test["linear_score"].to_numpy())
        folds.append(fold)
        selections.append({
            "held_out_participant": held_out,
            "selected_family": family,
            "selected_parameter": parameter,
            "training_objective_median_rho": objective,
        })
    return pd.concat(folds, ignore_index=True), pd.DataFrame(selections)


def paired_mae_summary(
    predictions: pd.DataFrame, left: str, right: str, rng: np.random.Generator
) -> dict[str, float]:
    left_mae = participant_mae(predictions, left)
    right_mae = participant_mae(predictions, right)
    difference = (left_mae - right_mae).to_numpy(dtype=float)
    boot = np.asarray([
        rng.choice(difference, len(difference), replace=True).mean()
        for _ in range(BOOTSTRAP_REPLICATES)
    ])
    return {
        "participants": int(len(difference)),
        "participant_balanced_mae_left": float(left_mae.mean()),
        "participant_balanced_mae_right": float(right_mae.mean()),
        "mae_difference_left_minus_right": float(difference.mean()),
        "ci_low": float(np.percentile(boot, 2.5)),
        "ci_high": float(np.percentile(boot, 97.5)),
        "participants_favoring_left": int((difference < 0).sum()),
    }


def rank_matrix(values: np.ndarray) -> np.ndarray:
    if values.ndim == 1:
        return pd.Series(values).rank(method="average").to_numpy(dtype=float)
    return np.column_stack([
        pd.Series(values[:, index]).rank(method="average").to_numpy(dtype=float)
        for index in range(values.shape[1])
    ])


def column_correlations(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x_centered = x - x.mean(axis=0, keepdims=True)
    y_centered = y - y.mean()
    numerator = np.sum(x_centered * y_centered[:, None], axis=0)
    denominator = np.sqrt(np.sum(x_centered**2, axis=0) * np.sum(y_centered**2))
    return np.divide(numerator, denominator, out=np.full(x.shape[1], np.nan), where=denominator > 0)


def permutation_negative_control(frame: pd.DataFrame, rng: np.random.Generator) -> dict[str, float]:
    lambdas = np.round(np.arange(0.0, 15.01, 0.1), 1)
    score_grid = np.column_stack([binned_tilt(frame, 10, lam) for lam in lambdas])
    participant_blocks = []
    observed_by_participant = []
    for participant, group in frame.groupby("participant", sort=True):
        if len(group) < MIN_SESSIONS:
            continue
        idx = group.index.to_numpy(dtype=int)
        x_rank = rank_matrix(score_grid[idx])
        y = group["rpe"].to_numpy(dtype=float)
        y_rank = rank_matrix(y)
        participant_blocks.append((str(participant), x_rank, y_rank))
        observed_by_participant.append(column_correlations(x_rank, y_rank))
    observed_curve = np.nanmedian(np.vstack(observed_by_participant), axis=0)
    observed_max = float(np.nanmax(observed_curve))
    observed_lambda = float(lambdas[np.flatnonzero(np.isclose(observed_curve, observed_max))[0]])
    locked_index = int(np.flatnonzero(np.isclose(lambdas, 6.2))[0])
    null_max = np.empty(PERMUTATION_REPLICATES, dtype=float)
    null_locked = np.empty(PERMUTATION_REPLICATES, dtype=float)
    for replicate in range(PERMUTATION_REPLICATES):
        participant_curves = []
        for _, x_rank, y_rank in participant_blocks:
            shift = int(rng.integers(1, len(y_rank)))
            permuted = np.roll(y_rank, shift)
            participant_curves.append(column_correlations(x_rank, permuted))
        curve = np.nanmedian(np.vstack(participant_curves), axis=0)
        null_max[replicate] = np.nanmax(curve)
        null_locked[replicate] = curve[locked_index]
    return {
        "eligible_participants": len(participant_blocks),
        "permutation_replicates": PERMUTATION_REPLICATES,
        "observed_selected_lambda": observed_lambda,
        "observed_maximum_median_within_participant_rho": observed_max,
        "selection_adjusted_empirical_p": float((1 + np.sum(null_max >= observed_max)) / (PERMUTATION_REPLICATES + 1)),
        "null_maximum_rho_95th_percentile": float(np.percentile(null_max, 95)),
        "observed_locked_lambda_median_rho": float(observed_curve[locked_index]),
        "locked_lambda_empirical_p": float((1 + np.sum(null_locked >= observed_curve[locked_index])) / (PERMUTATION_REPLICATES + 1)),
        "null_locked_rho_95th_percentile": float(np.percentile(null_locked, 95)),
    }


def descriptive_lambda_heterogeneity(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    strata = {
        "all": np.ones(len(frame), dtype=bool),
        "treadmill": frame["exercise_name"].eq("Treadmill").to_numpy(),
        "run": frame["exercise_name"].eq("Run").to_numpy(),
        "male": frame["sex"].eq("male").to_numpy(),
        "female": frame["sex"].eq("female").to_numpy(),
    }
    for stratum, mask in strata.items():
        subset = frame.loc[mask].copy()
        eligible = subset.groupby("participant").filter(lambda group: len(group) >= MIN_SESSIONS)
        if eligible["participant"].nunique() < 2:
            rows.append({"stratum": stratum, "sessions": len(subset), "eligible_participants": eligible["participant"].nunique(), "selected_lambda": np.nan})
            continue
        rows.append({
            "stratum": stratum,
            "sessions": len(subset),
            "eligible_participants": int(eligible["participant"].nunique()),
            "selected_lambda": float(select_lambda(eligible, "ten_bins")),
        })
    return pd.DataFrame(rows)


def main() -> None:
    rng = np.random.default_rng(RANDOM_SEED)
    primary = pd.read_csv(ANALYSIS / "pmdata_primary_analysis_sessions.csv")
    primary["participant"] = primary["participant"].astype(str)

    primary["matching_tier"] = np.where(
        primary["match_unique_both_directions"].astype(bool)
        & primary["report_delay_min"].between(15, 120)
        & (primary["duration_difference_min"] <= 10),
        "strict",
        "standard",
    )
    matching_summary = primary.groupby("matching_tier").agg(
        sessions=("session_number", "size"),
        participants=("participant", "nunique"),
        median_report_delay_min=("report_delay_min", "median"),
        median_duration_difference_min=("duration_difference_min", "median"),
    ).reset_index()

    strict = primary[primary["matching_tier"] == "strict"].copy()
    strict_predictions, strict_selections = nested_thrr_vs_linear(strict)
    strict_mae = paired_mae_summary(strict_predictions, "pred_thrr_i", "pred_linear", rng)

    selection_predictions, selection_table = selection_aware_nested(primary)
    selection_mae = paired_mae_summary(selection_predictions, "pred_selected_pipeline", "pred_linear", rng)
    family_counts = selection_table["selected_family"].value_counts().rename_axis("selected_family").reset_index(name="outer_folds")

    permutation = permutation_negative_control(primary, rng)
    heterogeneity = descriptive_lambda_heterogeneity(primary)

    matching_summary.to_csv(ANALYSIS / "reviewer_round4_matching_confidence.csv", index=False)
    strict_predictions.to_csv(ANALYSIS / "reviewer_round4_strict_matching_predictions.csv", index=False)
    strict_selections.to_csv(ANALYSIS / "reviewer_round4_strict_matching_parameters.csv", index=False)
    selection_predictions.to_csv(ANALYSIS / "reviewer_round4_selection_aware_predictions.csv", index=False)
    selection_table.to_csv(ANALYSIS / "reviewer_round4_selection_aware_parameters.csv", index=False)
    family_counts.to_csv(ANALYSIS / "reviewer_round4_selection_aware_family_counts.csv", index=False)
    heterogeneity.to_csv(ANALYSIS / "reviewer_round4_lambda_heterogeneity.csv", index=False)

    payload = {
        "matching_confidence": matching_summary.to_dict("records"),
        "strict_matching_nested_comparison": strict_mae,
        "selection_aware_nested_comparison": selection_mae,
        "selection_aware_family_counts": family_counts.to_dict("records"),
        "permutation_negative_control": permutation,
        "descriptive_lambda_heterogeneity": heterogeneity.to_dict("records"),
        "scope_note": "The selection-aware analysis re-runs transformation-family and parameter selection within each outer training fold. It remains conditional on the retrospectively defined candidate set.",
        "training_status_note": "Training-status heterogeneity was not estimated because PMData does not provide a sufficiently harmonized training-status variable for this session subset.",
        "random_seed": RANDOM_SEED,
    }
    (ANALYSIS / "reviewer_round4_analysis.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
