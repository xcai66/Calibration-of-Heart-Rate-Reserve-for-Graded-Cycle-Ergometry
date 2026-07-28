from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_whr_as_public_data import fit_weighted_line, predict_weighted_line, spearman_rho
from assess_pmdata_matching import BASE, candidate_pairs, greedy_unique_match


ROOT = Path(__file__).resolve().parent
ANALYSIS = ROOT / "analysis"
LAMBDA_GRID = np.round(np.arange(0.0, 15.01, 0.1), 1)
RANDOM_SEED = 20260729
BOOTSTRAP_REPLICATES = 5000
MIN_SESSIONS = 5


def binned_tilt(frame: pd.DataFrame, bin_count: int, lam: float, prefix: str | None = None) -> np.ndarray:
    if prefix is None:
        columns = [f"p{i}" for i in range(1, 11)] if bin_count == 10 else [f"p{bin_count}_{i}" for i in range(1, bin_count + 1)]
    else:
        columns = [f"{prefix}{i}" for i in range(1, bin_count + 1)]
    proportions = frame[columns].to_numpy(dtype=float)
    centers = (np.arange(1, bin_count + 1, dtype=float) - 0.5) / bin_count
    weights = np.exp(float(lam) * centers)
    return (proportions @ (centers * weights)) / (proportions @ weights)


def variant_score(frame: pd.DataFrame, variant: str, lam: float) -> np.ndarray:
    if variant == "five_bins":
        return binned_tilt(frame, 5, lam)
    if variant == "ten_bins":
        return binned_tilt(frame, 10, lam)
    if variant == "twenty_bins":
        return binned_tilt(frame, 20, lam)
    if variant == "continuous":
        return frame[f"continuous_tilt_l{int(round(lam * 10)):03d}"].to_numpy(dtype=float)
    if variant == "session_date_rest_ten_bins":
        return binned_tilt(frame, 10, lam, prefix="p10_daily_")
    raise KeyError(variant)


def participant_correlations(frame: pd.DataFrame, score: np.ndarray) -> dict[str, float]:
    working = frame[["participant", "rpe"]].copy()
    working["score"] = score
    output: dict[str, float] = {}
    for participant, group in working.groupby("participant"):
        if len(group) < MIN_SESSIONS:
            continue
        value = spearman_rho(group["score"].to_numpy(), group["rpe"].to_numpy())
        if np.isfinite(value):
            output[str(participant)] = float(value)
    return output


def select_lambda(frame: pd.DataFrame, variant: str) -> float:
    rows: list[tuple[float, float]] = []
    for lam in LAMBDA_GRID:
        correlations = participant_correlations(frame, variant_score(frame, variant, float(lam)))
        median = float(np.median(list(correlations.values()))) if correlations else float("nan")
        rows.append((float(lam), median))
    table = pd.DataFrame(rows, columns=["lambda", "median_rho"]).dropna()
    maximum = table["median_rho"].max()
    return float(table.loc[np.isclose(table["median_rho"], maximum), "lambda"].min())


def nested_variant(frame: pd.DataFrame, variant: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    folds = []
    parameters = []
    for held_out in sorted(frame["participant"].unique()):
        train = frame[frame["participant"] != held_out].copy()
        test = frame[frame["participant"] == held_out].copy()
        lam = select_lambda(train, variant)
        train_score = variant_score(train, variant, lam)
        test_score = variant_score(test, variant, lam)
        model = fit_weighted_line(train_score, train["rpe"].to_numpy(), train["participant"].to_numpy())
        fold = test[["participant", "session_number", "rpe"]].copy()
        fold["score"] = test_score
        fold["prediction"] = predict_weighted_line(model, test_score)
        fold["selected_lambda"] = lam
        folds.append(fold)
        parameters.append({"held_out_participant": held_out, "selected_lambda": lam})
    return pd.concat(folds, ignore_index=True), pd.DataFrame(parameters)


def summarize_variant(frame: pd.DataFrame, variant: str, rng: np.random.Generator) -> dict:
    predictions, parameters = nested_variant(frame, variant)
    participant_mae = predictions.groupby("participant").apply(
        lambda group: float(np.mean(np.abs(group["prediction"] - group["rpe"]))),
        include_groups=False,
    )
    eligible_rho = []
    for _, group in predictions.groupby("participant"):
        if len(group) >= MIN_SESSIONS:
            value = spearman_rho(group["score"].to_numpy(), group["rpe"].to_numpy())
            if np.isfinite(value):
                eligible_rho.append(value)
    boot_mae = np.array([
        rng.choice(participant_mae.to_numpy(), len(participant_mae), replace=True).mean()
        for _ in range(BOOTSTRAP_REPLICATES)
    ])
    return {
        "variant": variant,
        "sessions": int(len(frame)),
        "participants": int(frame["participant"].nunique()),
        "full_data_lambda": select_lambda(frame, variant),
        "outer_lambda_median": float(parameters["selected_lambda"].median()),
        "outer_lambda_q1": float(parameters["selected_lambda"].quantile(0.25)),
        "outer_lambda_q3": float(parameters["selected_lambda"].quantile(0.75)),
        "participant_balanced_mae": float(participant_mae.mean()),
        "mae_ci_low": float(np.percentile(boot_mae, 2.5)),
        "mae_ci_high": float(np.percentile(boot_mae, 97.5)),
        "participants_with_rho": int(len(eligible_rho)),
        "median_within_participant_rho": float(np.median(eligible_rho)),
    }


def repeated_grouped_split_sensitivity(primary: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Re-run lambda selection and calibration across 200 participant-level 12/3 splits."""
    participants = sorted(primary["participant"].unique())
    combinations = list(itertools.combinations(participants, 3))
    selected_indices = rng.choice(len(combinations), size=min(200, len(combinations)), replace=False)
    rows = []
    for split_number, index in enumerate(selected_indices, start=1):
        held_out = set(combinations[int(index)])
        train = primary[~primary["participant"].isin(held_out)].copy()
        test = primary[primary["participant"].isin(held_out)].copy()
        lam = select_lambda(train, "ten_bins")
        train_tilted = variant_score(train, "ten_bins", lam)
        test_tilted = variant_score(test, "ten_bins", lam)
        train_linear = train["linear_score"].to_numpy(dtype=float)
        test_linear = test["linear_score"].to_numpy(dtype=float)
        tilted_model = fit_weighted_line(train_tilted, train["rpe"].to_numpy(), train["participant"].to_numpy())
        linear_model = fit_weighted_line(train_linear, train["rpe"].to_numpy(), train["participant"].to_numpy())
        evaluated = test[["participant", "rpe"]].copy()
        evaluated["pred_tilted"] = predict_weighted_line(tilted_model, test_tilted)
        evaluated["pred_linear"] = predict_weighted_line(linear_model, test_linear)
        participant_differences = evaluated.groupby("participant").apply(
            lambda group: float(
                np.mean(np.abs(group["pred_tilted"] - group["rpe"]))
                - np.mean(np.abs(group["pred_linear"] - group["rpe"]))
            ),
            include_groups=False,
        )
        rows.append({
            "split": split_number,
            "held_out_participants": ";".join(sorted(held_out)),
            "selected_lambda": lam,
            "mae_difference_tilted_minus_linear": float(participant_differences.mean()),
            "held_out_participants_favoring_tilted": int((participant_differences < 0).sum()),
        })
    return pd.DataFrame(rows)


def matching_stability(primary: pd.DataFrame) -> pd.DataFrame:
    primary_keys = set(
        zip(primary["participant"].astype(str), primary["rpe_index"].astype(int), primary["exercise_index"].astype(int))
    )
    rules = [
        ("delay_15_180_min", 15.0, 180.0, None, "default"),
        ("delay_15_90_min", 15.0, 90.0, None, "default"),
        ("delay_30_120_min", 30.0, 120.0, None, "default"),
        ("delay_15_180_and_duration_le_10_min", 15.0, 180.0, 10.0, "default"),
        ("delay_priority_cost", 15.0, 180.0, None, "delay"),
        ("duration_priority_cost", 15.0, 180.0, None, "duration"),
    ]
    rows = []
    participants = sorted(primary["participant"].astype(str).unique())
    for name, low, high, duration_limit, cost_rule in rules:
        selected_keys: set[tuple[str, int, int]] = set()
        unique_keys: set[tuple[str, int, int]] = set()
        for participant in participants:
            candidates = candidate_pairs(participant)
            if candidates.empty:
                continue
            filtered = candidates[candidates["report_delay_min"].between(low, high)].copy()
            if duration_limit is not None:
                filtered = filtered[filtered["duration_difference_min"] <= duration_limit].copy()
            if filtered.empty:
                continue
            if cost_rule == "delay":
                filtered["cost"] = filtered["report_delay_min"].abs()
            elif cost_rule == "duration":
                filtered["cost"] = filtered["duration_difference_min"] / np.maximum(filtered["rpe_duration_min"], 10.0)
            rpe_counts = filtered.groupby("rpe_index").size()
            exercise_counts = filtered.groupby("exercise_index").size()
            selected = greedy_unique_match(filtered)
            for record in selected.to_dict("records"):
                key = (participant, int(record["rpe_index"]), int(record["exercise_index"]))
                selected_keys.add(key)
                if rpe_counts.loc[int(record["rpe_index"])] == 1 and exercise_counts.loc[int(record["exercise_index"])] == 1:
                    unique_keys.add(key)
        overlap = len(primary_keys & selected_keys)
        rows.append({
            "rule": name,
            "selected_pairs": len(selected_keys),
            "bidirectionally_unique_pairs": len(unique_keys),
            "primary_pairs_retained": overlap,
            "primary_pairs_retained_percent": 100.0 * overlap / len(primary_keys),
        })
    return pd.DataFrame(rows)


def auc_rank(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    positives = int(y.sum())
    negatives = int(len(y) - positives)
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = pd.Series(score).rank(method="average").to_numpy(dtype=float)
    return float((ranks[y == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def participant_balanced_high_rpe_auc(predictions: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for participant, group in predictions.groupby("participant"):
        y = (group["rpe"].to_numpy(dtype=float) >= 8).astype(int)
        if y.min() == y.max():
            continue
        rows.append({
            "participant": participant,
            "sessions": len(group),
            "high_rpe_sessions": int(y.sum()),
            "auc_tilted_hrr": auc_rank(y, group["pred_tilted_hrr"].to_numpy()),
            "auc_linear_decile": auc_rank(y, group["pred_linear_decile"].to_numpy()),
        })
    table = pd.DataFrame(rows)
    difference = table["auc_tilted_hrr"] - table["auc_linear_decile"]
    bootstrap = np.array([
        rng.choice(difference.to_numpy(), len(difference), replace=True).mean()
        for _ in range(BOOTSTRAP_REPLICATES)
    ])
    summary = pd.DataFrame([{
        "eligible_participants": len(table),
        "eligible_sessions": int(table["sessions"].sum()),
        "eligible_high_rpe_sessions": int(table["high_rpe_sessions"].sum()),
        "mean_participant_auc_tilted": float(table["auc_tilted_hrr"].mean()),
        "mean_participant_auc_linear": float(table["auc_linear_decile"].mean()),
        "mean_auc_difference": float(difference.mean()),
        "conditional_ci_low": float(np.percentile(bootstrap, 2.5)),
        "conditional_ci_high": float(np.percentile(bootstrap, 97.5)),
    }])
    table.to_csv(ANALYSIS / "reviewer_round2_participant_high_rpe_auc.csv", index=False)
    return summary


def quadratic_weighted_kappa(y: np.ndarray, prediction: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    prediction = np.clip(np.rint(prediction), 1, 10).astype(int)
    levels = np.arange(1, 11)
    observed = np.zeros((10, 10), dtype=float)
    for actual, fitted in zip(y, prediction):
        observed[actual - 1, fitted - 1] += 1
    actual_hist = observed.sum(axis=1)
    fitted_hist = observed.sum(axis=0)
    expected = np.outer(actual_hist, fitted_hist) / max(observed.sum(), 1.0)
    weights = ((levels[:, None] - levels[None, :]) / 9.0) ** 2
    denominator = float(np.sum(weights * expected))
    return 1.0 - float(np.sum(weights * observed)) / denominator if denominator > 0 else float("nan")


def ordinal_sensitivity(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for participant, group in predictions.groupby("participant"):
        if len(group) < MIN_SESSIONS or group["rpe"].nunique() < 2:
            continue
        rows.append({
            "participant": participant,
            "sessions": len(group),
            "kappa_tilted_hrr": quadratic_weighted_kappa(group["rpe"].to_numpy(), group["pred_tilted_hrr"].to_numpy()),
            "kappa_linear_decile": quadratic_weighted_kappa(group["rpe"].to_numpy(), group["pred_linear_decile"].to_numpy()),
        })
    table = pd.DataFrame(rows)
    return pd.DataFrame([{
        "eligible_participants": len(table),
        "median_quadratic_weighted_kappa_tilted": float(table["kappa_tilted_hrr"].median()),
        "median_quadratic_weighted_kappa_linear": float(table["kappa_linear_decile"].median()),
        "median_paired_difference": float((table["kappa_tilted_hrr"] - table["kappa_linear_decile"]).median()),
    }])


def matched_mean_examples(primary: pd.DataFrame, lam: float) -> pd.DataFrame:
    working = primary.copy()
    working["tHRR_I"] = variant_score(working, "ten_bins", lam)
    working["delta_tilt"] = working["tHRR_I"] - working["mean_hrr"]
    candidates = []
    for participant, group in working.groupby("participant"):
        records = group.to_dict("records")
        for left, right in itertools.combinations(records, 2):
            mean_difference = abs(float(left["mean_hrr"]) - float(right["mean_hrr"]))
            if mean_difference > 0.02:
                continue
            tilted_difference = abs(float(left["tHRR_I"]) - float(right["tHRR_I"]))
            candidates.append({
                "participant": participant,
                "session_a": int(left["session_number"]),
                "session_b": int(right["session_number"]),
                "mean_hrr_a": float(left["mean_hrr"]),
                "mean_hrr_b": float(right["mean_hrr"]),
                "tHRR_I_a": float(left["tHRR_I"]),
                "tHRR_I_b": float(right["tHRR_I"]),
                "delta_tilt_a": float(left["delta_tilt"]),
                "delta_tilt_b": float(right["delta_tilt"]),
                "rpe_a": float(left["rpe"]),
                "rpe_b": float(right["rpe"]),
                "absolute_mean_hrr_difference": mean_difference,
                "absolute_tilted_difference": tilted_difference,
            })
    return pd.DataFrame(candidates).sort_values("absolute_tilted_difference", ascending=False).head(10)


def main() -> None:
    rng = np.random.default_rng(RANDOM_SEED)
    primary = pd.read_csv(ANALYSIS / "pmdata_primary_analysis_sessions.csv")
    required = ["p5_1", "p20_1", "continuous_tilt_l000"]
    missing = [column for column in required if column not in primary.columns]
    if missing:
        raise RuntimeError(f"Re-run build_pmdata_session_dataset.py before this script; missing {missing}")

    variant_rows = [summarize_variant(primary, variant, rng) for variant in ["five_bins", "ten_bins", "twenty_bins", "continuous"]]
    daily = primary[primary["session_date_hrrest_available"].astype(bool)].dropna(subset=["p10_daily_1"]).copy()
    if daily["participant"].nunique() >= 3:
        variant_rows.append(summarize_variant(daily, "session_date_rest_ten_bins", rng))
    variant_table = pd.DataFrame(variant_rows)

    repeated_splits = repeated_grouped_split_sensitivity(primary, rng)
    matching = matching_stability(primary)
    predictions = pd.read_csv(ANALYSIS / "improved_formula_nested_predictions.csv")
    high_rpe = participant_balanced_high_rpe_auc(predictions, rng)
    ordinal = ordinal_sensitivity(predictions)
    lam = float(variant_table.loc[variant_table["variant"] == "ten_bins", "full_data_lambda"].iloc[0])
    examples = matched_mean_examples(primary, lam)
    clipping = pd.DataFrame([{
        "sessions": len(primary),
        "weighted_hrr_below_zero_percent": 100.0 * float(np.average(primary["hrr_below_zero_fraction"], weights=primary["valid_hr_minutes"])),
        "weighted_hrr_above_one_percent": 100.0 * float(np.average(primary["hrr_above_one_fraction"], weights=primary["valid_hr_minutes"])),
        "sessions_with_any_below_zero": int((primary["hrr_below_zero_fraction"] > 0).sum()),
        "sessions_with_any_above_one": int((primary["hrr_above_one_fraction"] > 0).sum()),
        "sessions_with_session_date_resting_hr": int(primary["session_date_hrrest_available"].astype(bool).sum()),
    }])
    prediction_range = pd.DataFrame([{
        "model": model,
        "minimum_prediction": float(predictions[f"pred_{model}"].min()),
        "maximum_prediction": float(predictions[f"pred_{model}"].max()),
        "outside_1_to_10": int(((predictions[f"pred_{model}"] < 1) | (predictions[f"pred_{model}"] > 10)).sum()),
    } for model in ["tilted_hrr", "linear_decile", "mean_hrr", "intercept_only"]])

    split_summary = pd.DataFrame([{
        "splits": len(repeated_splits),
        "median_selected_lambda": float(repeated_splits["selected_lambda"].median()),
        "lambda_q1": float(repeated_splits["selected_lambda"].quantile(0.25)),
        "lambda_q3": float(repeated_splits["selected_lambda"].quantile(0.75)),
        "median_mae_difference": float(repeated_splits["mae_difference_tilted_minus_linear"].median()),
        "mae_difference_q1": float(repeated_splits["mae_difference_tilted_minus_linear"].quantile(0.25)),
        "mae_difference_q3": float(repeated_splits["mae_difference_tilted_minus_linear"].quantile(0.75)),
        "splits_favoring_tilted_percent": 100.0 * float((repeated_splits["mae_difference_tilted_minus_linear"] < 0).mean()),
    }])

    outputs = {
        "reviewer_round2_discretization_sensitivity.csv": variant_table,
        "reviewer_round2_repeated_grouped_splits.csv": repeated_splits,
        "reviewer_round2_repeated_grouped_splits_summary.csv": split_summary,
        "reviewer_round2_matching_stability.csv": matching,
        "reviewer_round2_participant_balanced_high_rpe_auc.csv": high_rpe,
        "reviewer_round2_ordinal_sensitivity.csv": ordinal,
        "reviewer_round2_matched_mean_examples.csv": examples,
        "reviewer_round2_hrr_clipping.csv": clipping,
        "reviewer_round2_prediction_range.csv": prediction_range,
    }
    for filename, table in outputs.items():
        table.to_csv(ANALYSIS / filename, index=False)
    payload = {
        "discretization_sensitivity": variant_table.to_dict("records"),
        "repeated_grouped_split_summary": split_summary.to_dict("records"),
        "matching_stability": matching.to_dict("records"),
        "participant_balanced_high_rpe_auc": high_rpe.to_dict("records"),
        "ordinal_sensitivity": ordinal.to_dict("records"),
        "hrr_clipping": clipping.to_dict("records"),
        "prediction_range": prediction_range.to_dict("records"),
        "analysis_hierarchy": {
            "primary_comparison": "ten-bin tHRR-I versus linear decile score for participant-balanced held-out MAE",
            "secondary_analyses": "within-participant Spearman association and intercept-only comparison",
            "exploratory_analyses": "other formula families, high-RPE discrimination, load, discretization, matching, and anchor sensitivities",
            "multiplicity": "No confirmatory p values are claimed; all intervals are descriptive and conditional on development choices.",
        },
        "repeated_split_note": "Each of 200 participant-level 12/3 splits repeated lambda selection and calibration for the locked ten-bin tHRR-I family and the linear comparator. Quantiles describe split sensitivity and are not external-validation confidence intervals.",
        "random_seed": RANDOM_SEED,
    }
    (ANALYSIS / "reviewer_round2_analysis.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
