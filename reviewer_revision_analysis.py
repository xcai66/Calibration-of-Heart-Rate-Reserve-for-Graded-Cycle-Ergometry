from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
ANALYSIS = ROOT / "analysis"
BOOTSTRAP_REPLICATES = 5000
RANDOM_SEED = 20260731
CENTERS = (np.arange(1, 11, dtype=float) - 0.5) / 10.0


def participant_balanced_intercept(training: pd.DataFrame) -> float:
    """Mean of participant-specific mean RPE values."""
    return float(training.groupby("participant")["rpe"].mean().mean())


def auc_rank(y: np.ndarray, score: np.ndarray) -> float:
    """Mann-Whitney representation of the ROC area, including average ranks for ties."""
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    n_positive = int(y.sum())
    n_negative = int(len(y) - n_positive)
    if n_positive == 0 or n_negative == 0:
        return float("nan")
    ranks = pd.Series(score).rank(method="average").to_numpy(dtype=float)
    return float(
        (ranks[y == 1].sum() - n_positive * (n_positive + 1) / 2)
        / (n_positive * n_negative)
    )


def percentile_interval(values: np.ndarray) -> tuple[float, float]:
    return float(np.nanpercentile(values, 2.5)), float(np.nanpercentile(values, 97.5))


def participant_mae(frame: pd.DataFrame, prediction_column: str) -> pd.Series:
    return frame.groupby("participant", sort=True).apply(
        lambda group: float(np.mean(np.abs(group[prediction_column] - group["rpe"]))),
        include_groups=False,
    )


def add_intercept_predictions(primary: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    output = predictions.copy()
    output["score_intercept_only"] = 0.0
    output["pred_intercept_only"] = np.nan
    for participant in sorted(primary["participant"].unique()):
        training = primary[primary["participant"] != participant]
        value = participant_balanced_intercept(training)
        output.loc[output["participant"] == participant, "pred_intercept_only"] = value
    return output


def paired_mae_comparisons(predictions: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    reference = participant_mae(predictions, "pred_tilted_hrr")
    comparators = [
        "intercept_only",
        "linear_decile",
        "mean_hrr",
        "entropic_hrr",
        "power_hrr",
        "original_exp",
        "banister_trimp",
    ]
    rows = []
    for comparator in comparators:
        other = participant_mae(predictions, f"pred_{comparator}")
        difference = reference - other
        bootstrap = np.array(
            [rng.choice(difference.to_numpy(), len(difference), replace=True).mean()
             for _ in range(BOOTSTRAP_REPLICATES)]
        )
        low, high = percentile_interval(bootstrap)
        rows.append(
            {
                "comparison": f"tilted_hrr_minus_{comparator}",
                "participants": len(difference),
                "tilted_participant_balanced_mae": float(reference.mean()),
                "comparator_participant_balanced_mae": float(other.mean()),
                "mae_difference": float(difference.mean()),
                "conditional_ci_low": low,
                "conditional_ci_high": high,
                "participants_improved": int((difference < 0).sum()),
                "participants_unchanged": int(np.isclose(difference, 0).sum()),
                "participants_worsened": int((difference > 0).sum()),
            }
        )
    return pd.DataFrame(rows)


def minimum_session_sensitivity(predictions: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    counts = predictions.groupby("participant").size()
    eligible = counts[counts >= 5].index
    frame = predictions[predictions["participant"].isin(eligible)].copy()
    tilted = participant_mae(frame, "pred_tilted_hrr")
    linear = participant_mae(frame, "pred_linear_decile")
    difference = tilted - linear
    bootstrap = np.array(
        [rng.choice(difference.to_numpy(), len(difference), replace=True).mean()
         for _ in range(BOOTSTRAP_REPLICATES)]
    )
    low, high = percentile_interval(bootstrap)
    return pd.DataFrame(
        [
            {
                "minimum_sessions": 5,
                "participants": len(eligible),
                "sessions": len(frame),
                "tilted_participant_balanced_mae": float(tilted.mean()),
                "linear_participant_balanced_mae": float(linear.mean()),
                "mae_difference": float(difference.mean()),
                "conditional_ci_low": low,
                "conditional_ci_high": high,
            }
        ]
    )


def intercept_performance(predictions: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    groups = {key: group for key, group in predictions.groupby("participant")}
    participants = np.array(sorted(groups), dtype=object)

    def calculate(sampled: np.ndarray) -> tuple[float, float, float]:
        participant_maes = []
        participant_mses = []
        observed = []
        predicted = []
        for participant in sampled:
            group = groups[str(participant)]
            y = group["rpe"].to_numpy(dtype=float)
            pred = group["pred_intercept_only"].to_numpy(dtype=float)
            error = pred - y
            participant_maes.append(float(np.mean(np.abs(error))))
            participant_mses.append(float(np.mean(error**2)))
            observed.append(y)
            predicted.append(pred)
        y_all = np.concatenate(observed)
        pred_all = np.concatenate(predicted)
        denominator = float(np.sum((y_all - np.mean(y_all)) ** 2))
        r2 = 1.0 - float(np.sum((y_all - pred_all) ** 2)) / denominator if denominator > 0 else float("nan")
        return float(np.mean(participant_maes)), float(np.sqrt(np.mean(participant_mses))), r2

    estimate = calculate(participants)
    bootstrap = np.empty((BOOTSTRAP_REPLICATES, 3), dtype=float)
    for index in range(BOOTSTRAP_REPLICATES):
        bootstrap[index] = calculate(rng.choice(participants, len(participants), replace=True))
    intervals = [percentile_interval(bootstrap[:, index]) for index in range(3)]
    return pd.DataFrame(
        [
            {
                "family": "intercept_only",
                "participants": len(participants),
                "participant_balanced_mae": estimate[0],
                "mae_ci_low": intervals[0][0],
                "mae_ci_high": intervals[0][1],
                "participant_balanced_rmse": estimate[1],
                "rmse_ci_low": intervals[1][0],
                "rmse_ci_high": intervals[1][1],
                "pooled_cv_r2": estimate[2],
                "r2_ci_low": intervals[2][0],
                "r2_ci_high": intervals[2][1],
            }
        ]
    )


def high_rpe_discrimination(predictions: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Exploratory discrimination of an operational high-RPE threshold (RPE >= 8)."""
    frame = predictions.copy()
    frame["high_rpe"] = (frame["rpe"] >= 8).astype(int)
    groups = {key: group for key, group in frame.groupby("participant")}
    participants = np.array(sorted(groups), dtype=object)
    families = ["tilted_hrr", "linear_decile", "mean_hrr", "entropic_hrr", "power_hrr"]
    observed = {
        family: auc_rank(frame["high_rpe"].to_numpy(), frame[f"pred_{family}"].to_numpy())
        for family in families
    }
    boot = {family: np.empty(BOOTSTRAP_REPLICATES, dtype=float) for family in families}
    boot_difference = np.empty(BOOTSTRAP_REPLICATES, dtype=float)
    for index in range(BOOTSTRAP_REPLICATES):
        sampled = rng.choice(participants, len(participants), replace=True)
        sample = pd.concat([groups[str(participant)] for participant in sampled], ignore_index=True)
        y = sample["high_rpe"].to_numpy()
        for family in families:
            boot[family][index] = auc_rank(y, sample[f"pred_{family}"].to_numpy())
        boot_difference[index] = boot["tilted_hrr"][index] - boot["linear_decile"][index]
    summary_rows = []
    for family in families:
        low, high = percentile_interval(boot[family])
        summary_rows.append(
            {
                "family": family,
                "sessions": len(frame),
                "high_rpe_sessions": int(frame["high_rpe"].sum()),
                "roc_auc": observed[family],
                "conditional_ci_low": low,
                "conditional_ci_high": high,
            }
        )
    low, high = percentile_interval(boot_difference)
    comparison = pd.DataFrame(
        [
            {
                "comparison": "tilted_hrr_minus_linear_decile",
                "roc_auc_difference": observed["tilted_hrr"] - observed["linear_decile"],
                "conditional_ci_low": low,
                "conditional_ci_high": high,
            }
        ]
    )
    return pd.DataFrame(summary_rows), comparison


def tail_amplification_summary(primary: pd.DataFrame) -> pd.DataFrame:
    full_parameters = pd.read_csv(ANALYSIS / "improved_formula_full_parameters.csv")
    lam = float(full_parameters.loc[full_parameters["family"] == "tilted_hrr", "selected_parameter"].iloc[0])
    proportions = primary[[f"p{i}" for i in range(1, 11)]].to_numpy(dtype=float)
    weights = np.exp(lam * CENTERS)
    mean_midpoint = proportions @ CENTERS
    tilted = (proportions @ (CENTERS * weights)) / (proportions @ weights)
    delta = tilted - mean_midpoint
    tail_load_increment = primary["exercise_duration_min"].to_numpy(dtype=float) * delta
    rows = []
    for name, values in [
        ("mean_decile_midpoint", mean_midpoint),
        ("tHRR-I", tilted),
        ("delta_tilt", delta),
        ("duration_times_delta_tilt", tail_load_increment),
    ]:
        rows.append(
            {
                "quantity": name,
                "sessions": len(primary),
                "median": float(np.median(values)),
                "q1": float(np.quantile(values, 0.25)),
                "q3": float(np.quantile(values, 0.75)),
                "minimum": float(np.min(values)),
                "maximum": float(np.max(values)),
            }
        )
    rows.append(
        {
            "quantity": "adjacent_decile_weight_multiplier",
            "sessions": len(primary),
            "median": float(np.exp(lam / 10.0)),
            "q1": np.nan,
            "q3": np.nan,
            "minimum": np.nan,
            "maximum": np.nan,
        }
    )
    return pd.DataFrame(rows)


def attrition_audit() -> pd.DataFrame:
    frame = pd.read_csv(ANALYSIS / "pmdata_session_level_qc.csv")
    unique = frame[frame["match_unique_both_directions"].astype(bool)]
    unique_hr_qc = unique[unique["hr_qc_primary"].astype(bool)]
    primary = frame[frame["analysis_primary"].astype(bool)]
    excluded = frame[~frame["analysis_primary"].astype(bool)]
    return pd.DataFrame(
        [
            {"quantity": "tracker_linked_pairs", "value": len(frame)},
            {"quantity": "bidirectionally_unique_pairs", "value": len(unique)},
            {"quantity": "unique_pairs_passing_hr_qc", "value": len(unique_hr_qc)},
            {"quantity": "primary_sessions", "value": len(primary)},
            {"quantity": "primary_mean_rpe", "value": float(primary["rpe"].mean())},
            {"quantity": "excluded_mean_rpe", "value": float(excluded["rpe"].mean())},
            {"quantity": "primary_median_report_delay_min", "value": float(primary["report_delay_min"].median())},
            {"quantity": "primary_median_duration_difference_min", "value": float(primary["duration_difference_min"].median())},
            {"quantity": "primary_run_or_treadmill_sessions", "value": int(primary["exercise_name"].isin(["Run", "Treadmill"]).sum())},
        ]
    )


def main() -> None:
    rng = np.random.default_rng(RANDOM_SEED)
    primary = pd.read_csv(ANALYSIS / "pmdata_primary_analysis_sessions.csv")
    predictions = pd.read_csv(ANALYSIS / "improved_formula_nested_predictions.csv")
    predictions = add_intercept_predictions(primary, predictions)
    predictions.to_csv(ANALYSIS / "improved_formula_nested_predictions.csv", index=False)

    pairwise = paired_mae_comparisons(predictions, rng)
    min_sessions = minimum_session_sensitivity(predictions, rng)
    intercept = intercept_performance(predictions, rng)
    high_rpe, high_rpe_comparison = high_rpe_discrimination(predictions, rng)
    tail = tail_amplification_summary(primary)
    attrition = attrition_audit()

    outputs = {
        "reviewer_revision_pairwise_mae.csv": pairwise,
        "reviewer_revision_minimum_sessions.csv": min_sessions,
        "reviewer_revision_intercept_performance.csv": intercept,
        "reviewer_revision_high_rpe_auc.csv": high_rpe,
        "reviewer_revision_high_rpe_comparison.csv": high_rpe_comparison,
        "reviewer_revision_tail_amplification.csv": tail,
        "reviewer_revision_attrition_audit.csv": attrition,
    }
    for filename, table in outputs.items():
        table.to_csv(ANALYSIS / filename, index=False)

    payload = {
        "pairwise_mae": pairwise.to_dict("records"),
        "minimum_session_sensitivity": min_sessions.to_dict("records"),
        "intercept_performance": intercept.to_dict("records"),
        "high_rpe_auc": high_rpe.to_dict("records"),
        "high_rpe_comparison": high_rpe_comparison.to_dict("records"),
        "tail_amplification": tail.to_dict("records"),
        "attrition_audit": attrition.to_dict("records"),
        "uncertainty_note": (
            "Intervals are conditional participant-cluster bootstrap intervals for the realized held-out predictions. "
            "They do not repeat formula-family selection or the complete development pipeline."
        ),
        "high_rpe_note": "RPE >= 8 was an operational, post hoc threshold used only for exploratory discrimination analysis.",
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "random_seed": RANDOM_SEED,
    }
    (ANALYSIS / "reviewer_revision_analysis.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
