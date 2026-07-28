from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
ANALYSIS = ROOT / "analysis"
GRID = np.round(np.arange(0.01, 1.501, 0.01), 2)
BIN_INDEX = np.arange(1, 11, dtype=float)
BOOTSTRAP_REPLICATES = 5000
RANDOM_SEED = 20260727
MIN_ASSOCIATION_SESSIONS = 5


def spearman_rho(x: np.ndarray, y: np.ndarray) -> float:
    x_rank = pd.Series(np.asarray(x, dtype=float)).rank(method="average").to_numpy()
    y_rank = pd.Series(np.asarray(y, dtype=float)).rank(method="average").to_numpy()
    if np.std(x_rank) == 0 or np.std(y_rank) == 0:
        return float("nan")
    return float(np.corrcoef(x_rank, y_rank)[0, 1])


def nonlinear_score(frame: pd.DataFrame, k: float) -> np.ndarray:
    proportions = frame[[f"p{index}" for index in range(1, 11)]].to_numpy(dtype=float)
    weights = np.exp(k * BIN_INDEX)
    return proportions @ weights


def participant_rhos(
    frame: pd.DataFrame,
    score: np.ndarray,
    min_sessions: int = MIN_ASSOCIATION_SESSIONS,
) -> dict[str, float]:
    working = frame.copy()
    working["_score"] = score
    correlations: dict[str, float] = {}
    for participant, group in working.groupby("participant"):
        if len(group) < min_sessions:
            continue
        rho = spearman_rho(group["_score"].to_numpy(), group["rpe"].to_numpy())
        if math.isfinite(rho):
            correlations[str(participant)] = rho
    return correlations


def summarize_rhos(correlations: dict[str, float], session_counts: dict[str, int]) -> dict:
    if not correlations:
        return {
            "median_participant_rho": float("nan"),
            "mean_fisher_rho": float("nan"),
            "precision_weighted_fisher_rho": float("nan"),
        }
    values = np.array(list(correlations.values()), dtype=float)
    clipped = np.clip(values, -0.999999, 0.999999)
    fisher = np.arctanh(clipped)
    weights = np.array([max(session_counts[participant] - 3, 1) for participant in correlations], dtype=float)
    return {
        "median_participant_rho": float(np.median(values)),
        "mean_fisher_rho": float(np.tanh(np.mean(fisher))),
        "precision_weighted_fisher_rho": float(np.tanh(np.average(fisher, weights=weights))),
    }


def select_k(frame: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    session_counts = frame.groupby("participant").size().astype(int).to_dict()
    rows = []
    for k in GRID:
        correlations = participant_rhos(frame, nonlinear_score(frame, float(k)))
        row = {"k": float(k), "participants": len(correlations)}
        row.update(summarize_rhos(correlations, session_counts))
        rows.append(row)
    profile = pd.DataFrame(rows)
    valid = profile.dropna(subset=["median_participant_rho"])
    if valid.empty:
        raise ValueError("No participants with enough sessions for k selection")
    maximum = valid["median_participant_rho"].max()
    selected = float(valid.loc[np.isclose(valid["median_participant_rho"], maximum), "k"].min())
    return selected, profile


def fit_weighted_line(x: np.ndarray, y: np.ndarray, participants: np.ndarray) -> dict:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    participants = np.asarray(participants)
    counts = pd.Series(participants).value_counts().to_dict()
    weights = np.array([1.0 / counts[value] for value in participants], dtype=float)
    weighted_mean = float(np.average(x, weights=weights))
    weighted_sd = float(np.sqrt(np.average((x - weighted_mean) ** 2, weights=weights)))
    if not math.isfinite(weighted_sd) or weighted_sd <= 1e-12:
        weighted_sd = 1.0
    z = (x - weighted_mean) / weighted_sd
    design = np.column_stack([np.ones_like(z), z])
    root_w = np.sqrt(weights)
    beta, *_ = np.linalg.lstsq(design * root_w[:, None], y * root_w, rcond=None)
    return {"mean": weighted_mean, "sd": weighted_sd, "intercept": float(beta[0]), "slope": float(beta[1])}


def predict_weighted_line(model: dict, x: np.ndarray) -> np.ndarray:
    z = (np.asarray(x, dtype=float) - model["mean"]) / model["sd"]
    return model["intercept"] + model["slope"] * z


def nested_leave_one_participant_out(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    predictions = []
    k_rows = []
    participants = sorted(frame["participant"].unique())
    for held_out in participants:
        train = frame[frame["participant"] != held_out].copy()
        test = frame[frame["participant"] == held_out].copy()
        selected_k, _ = select_k(train)
        k_rows.append(
            {
                "held_out_participant": held_out,
                "selected_k": selected_k,
                "training_participants": train["participant"].nunique(),
                "training_sessions": len(train),
                "test_sessions": len(test),
            }
        )
        metric_values_train = {
            "nonlinear": nonlinear_score(train, selected_k),
            "linear": train["linear_score"].to_numpy(dtype=float),
            "mean_hrr": train["mean_hrr"].to_numpy(dtype=float),
            "banister_trimp": train["banister_trimp_integral"].to_numpy(dtype=float),
        }
        metric_values_test = {
            "nonlinear": nonlinear_score(test, selected_k),
            "linear": test["linear_score"].to_numpy(dtype=float),
            "mean_hrr": test["mean_hrr"].to_numpy(dtype=float),
            "banister_trimp": test["banister_trimp_integral"].to_numpy(dtype=float),
        }
        fold = test[
            [
                "participant",
                "session_number",
                "exercise_start_local",
                "exercise_name",
                "rpe",
                "rpe_duration_min",
            ]
        ].copy()
        fold["selected_k"] = selected_k
        for metric, train_values in metric_values_train.items():
            model = fit_weighted_line(
                train_values,
                train["rpe"].to_numpy(dtype=float),
                train["participant"].to_numpy(),
            )
            fold[f"score_{metric}"] = metric_values_test[metric]
            fold[f"pred_{metric}"] = predict_weighted_line(model, metric_values_test[metric])
        predictions.append(fold)
    return pd.concat(predictions, ignore_index=True), pd.DataFrame(k_rows)


def cluster_bootstrap_predictions(
    predictions: pd.DataFrame, metric: str, rng: np.random.Generator
) -> dict:
    groups = {participant: group for participant, group in predictions.groupby("participant")}
    participants = np.array(sorted(groups), dtype=object)

    def calculate(sampled: np.ndarray) -> tuple[float, float, float]:
        absolute_errors = []
        squared_errors = []
        y_values = []
        predicted_values = []
        for participant in sampled:
            group = groups[str(participant)]
            error = group[f"pred_{metric}"].to_numpy(dtype=float) - group["rpe"].to_numpy(dtype=float)
            absolute_errors.append(float(np.mean(np.abs(error))))
            squared_errors.append(float(np.mean(error**2)))
            y_values.append(group["rpe"].to_numpy(dtype=float))
            predicted_values.append(group[f"pred_{metric}"].to_numpy(dtype=float))
        y = np.concatenate(y_values)
        pred = np.concatenate(predicted_values)
        mae_balanced = float(np.mean(absolute_errors))
        rmse_balanced = float(np.sqrt(np.mean(squared_errors)))
        denominator = float(np.sum((y - np.mean(y)) ** 2))
        r2 = float(1.0 - np.sum((y - pred) ** 2) / denominator) if denominator > 0 else float("nan")
        return mae_balanced, rmse_balanced, r2

    observed = calculate(participants)
    bootstrap = np.empty((BOOTSTRAP_REPLICATES, 3), dtype=float)
    for index in range(BOOTSTRAP_REPLICATES):
        sampled = rng.choice(participants, size=len(participants), replace=True)
        bootstrap[index] = calculate(sampled)
    names = ["participant_balanced_mae", "participant_balanced_rmse", "pooled_cv_r2"]
    output = {}
    for column, name in enumerate(names):
        output[name] = observed[column]
        output[f"{name}_ci_low"] = float(np.nanpercentile(bootstrap[:, column], 2.5))
        output[f"{name}_ci_high"] = float(np.nanpercentile(bootstrap[:, column], 97.5))
    return output


def participant_associations(frame: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    scores = predictions.set_index(["participant", "session_number"])
    rows = []
    for participant, group in frame.groupby("participant"):
        if len(group) < MIN_ASSOCIATION_SESSIONS:
            continue
        indexed = group.set_index(["participant", "session_number"])
        corresponding = scores.loc[indexed.index]
        row = {"participant": participant, "sessions": len(group)}
        for metric in ["nonlinear", "linear", "mean_hrr", "banister_trimp"]:
            values = corresponding[f"score_{metric}"].to_numpy(dtype=float)
            row[f"rho_{metric}"] = spearman_rho(values, group["rpe"].to_numpy(dtype=float))
        rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_association_summary(associations: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics = ["nonlinear", "linear", "mean_hrr", "banister_trimp"]
    summary_rows = []
    for metric in metrics:
        values = associations[f"rho_{metric}"].to_numpy(dtype=float)
        observed = float(np.median(values))
        boot = np.empty(BOOTSTRAP_REPLICATES, dtype=float)
        for index in range(BOOTSTRAP_REPLICATES):
            sample = rng.choice(values, size=len(values), replace=True)
            boot[index] = np.median(sample)
        summary_rows.append(
            {
                "metric": metric,
                "participants": len(values),
                "median_participant_rho": observed,
                "ci_low": float(np.percentile(boot, 2.5)),
                "ci_high": float(np.percentile(boot, 97.5)),
                "mean_participant_rho": float(np.mean(values)),
            }
        )

    comparison_rows = []
    nonlinear_values = associations["rho_nonlinear"].to_numpy(dtype=float)
    for comparator in ["linear", "mean_hrr", "banister_trimp"]:
        comparator_values = associations[f"rho_{comparator}"].to_numpy(dtype=float)
        differences = nonlinear_values - comparator_values
        observed = float(np.median(differences))
        boot = np.empty(BOOTSTRAP_REPLICATES, dtype=float)
        for index in range(BOOTSTRAP_REPLICATES):
            boot[index] = float(np.median(rng.choice(differences, size=len(differences), replace=True)))
        comparison_rows.append(
            {
                "comparison": f"nonlinear_minus_{comparator}",
                "scale": "median paired difference in participant-level Spearman rho",
                "estimate": observed,
                "ci_low": float(np.percentile(boot, 2.5)),
                "ci_high": float(np.percentile(boot, 97.5)),
                "participants": len(differences),
            }
        )
    return pd.DataFrame(summary_rows), pd.DataFrame(comparison_rows)


def bootstrap_prediction_comparisons(predictions: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    per_participant = []
    for participant, group in predictions.groupby("participant"):
        row = {"participant": participant}
        for metric in ["nonlinear", "linear", "mean_hrr", "banister_trimp"]:
            row[f"mae_{metric}"] = float(
                np.mean(np.abs(group[f"pred_{metric}"].to_numpy(dtype=float) - group["rpe"].to_numpy(dtype=float)))
            )
        per_participant.append(row)
    table = pd.DataFrame(per_participant)
    rows = []
    for comparator in ["linear", "mean_hrr", "banister_trimp"]:
        differences = table["mae_nonlinear"].to_numpy() - table[f"mae_{comparator}"].to_numpy()
        boot = np.empty(BOOTSTRAP_REPLICATES, dtype=float)
        for index in range(BOOTSTRAP_REPLICATES):
            boot[index] = float(np.mean(rng.choice(differences, size=len(differences), replace=True)))
        rows.append(
            {
                "comparison": f"nonlinear_minus_{comparator}",
                "scale": "participant-balanced MAE difference (RPE units; negative favors nonlinear)",
                "estimate": float(np.mean(differences)),
                "ci_low": float(np.percentile(boot, 2.5)),
                "ci_high": float(np.percentile(boot, 97.5)),
                "participants": len(differences),
            }
        )
    return pd.DataFrame(rows)


def run_sensitivity(name: str, frame: pd.DataFrame, rng: np.random.Generator) -> dict:
    eligible = frame.groupby("participant").filter(
        lambda group: len(group) >= MIN_ASSOCIATION_SESSIONS
    ).copy()
    if eligible["participant"].nunique() < 3:
        return {"analysis": name, "sessions": len(frame), "participants": frame["participant"].nunique()}
    k, _ = select_k(eligible)
    nonlinear_by_participant = participant_rhos(eligible, nonlinear_score(eligible, k))
    linear_by_participant = participant_rhos(eligible, eligible["linear_score"].to_numpy(dtype=float))
    nonlinear_rho = float(np.median(list(nonlinear_by_participant.values())))
    linear_rho = float(np.median(list(linear_by_participant.values())))
    common = sorted(set(nonlinear_by_participant) & set(linear_by_participant))
    differences = np.array(
        [
            nonlinear_by_participant[p] - linear_by_participant[p]
            for p in common
        ]
    )
    boot = np.empty(BOOTSTRAP_REPLICATES, dtype=float)
    for index in range(BOOTSTRAP_REPLICATES):
        boot[index] = float(np.median(rng.choice(differences, size=len(differences), replace=True)))
    return {
        "analysis": name,
        "sessions": len(eligible),
        "participants": eligible["participant"].nunique(),
        "selected_k": k,
        "nonlinear_median_participant_rho": nonlinear_rho,
        "linear_median_participant_rho": linear_rho,
        "median_paired_rho_difference": float(np.median(differences)),
        "difference_ci_low": float(np.percentile(boot, 2.5)),
        "difference_ci_high": float(np.percentile(boot, 97.5)),
    }


def main() -> None:
    rng = np.random.default_rng(RANDOM_SEED)
    primary = pd.read_csv(ANALYSIS / "pmdata_primary_analysis_sessions.csv")
    primary["participant"] = primary["participant"].astype(str)
    final_k, profile = select_k(primary)
    profile.to_csv(ANALYSIS / "k_profile.csv", index=False)

    predictions, outer_k = nested_leave_one_participant_out(primary)
    predictions.to_csv(ANALYSIS / "nested_cv_predictions.csv", index=False)
    outer_k.to_csv(ANALYSIS / "k_selection_by_outer_fold.csv", index=False)

    performance_rows = []
    for metric in ["nonlinear", "linear", "mean_hrr", "banister_trimp"]:
        row = {"metric": metric}
        row.update(cluster_bootstrap_predictions(predictions, metric, rng))
        performance_rows.append(row)
    performance = pd.DataFrame(performance_rows)
    performance.to_csv(ANALYSIS / "nested_cv_performance.csv", index=False)

    associations = participant_associations(primary, predictions)
    associations.to_csv(ANALYSIS / "participant_level_associations.csv", index=False)
    association_summary, association_comparisons = bootstrap_association_summary(associations, rng)
    association_summary.to_csv(ANALYSIS / "association_summary.csv", index=False)

    prediction_comparisons = bootstrap_prediction_comparisons(predictions, rng)
    comparisons = pd.concat([association_comparisons, prediction_comparisons], ignore_index=True)
    comparisons.to_csv(ANALYSIS / "paired_model_comparisons.csv", index=False)

    broad = pd.read_csv(ANALYSIS / "pmdata_session_level_qc.csv")
    broad = broad[
        broad["rpe_valid"].astype(bool)
        & broad["hr_qc_primary"].astype(bool)
        & broad["report_delay_min"].between(0, 720)
    ].copy()
    sensitivity_rows = [
        run_sensitivity("primary", primary, rng),
        run_sensitivity(
            "measured_hrmax_only",
            primary[primary["measured_hrmax_available"].astype(bool)].copy(),
            rng,
        ),
        run_sensitivity(
            "exclude_sessions_with_gt5pct_hrr_above_one",
            primary[primary["hrr_above_one_fraction"] <= 0.05].copy(),
            rng,
        ),
        run_sensitivity("broad_matching_0_to_12h", broad, rng),
    ]
    sensitivity = pd.DataFrame(sensitivity_rows)
    sensitivity.to_csv(ANALYSIS / "sensitivity_analyses.csv", index=False)

    summary = {
        "primary_sessions": int(len(primary)),
        "primary_participants": int(primary["participant"].nunique()),
        "participants_with_at_least_5_sessions": int(associations["participant"].nunique()),
        "final_k_selected_on_all_primary_data": final_k,
        "outer_fold_k_median": float(outer_k["selected_k"].median()),
        "outer_fold_k_iqr": [
            float(outer_k["selected_k"].quantile(0.25)),
            float(outer_k["selected_k"].quantile(0.75)),
        ],
        "association_summary": association_summary.to_dict("records"),
        "nested_cv_performance": performance.to_dict("records"),
        "paired_comparisons": comparisons.to_dict("records"),
        "sensitivity_analyses": sensitivity.to_dict("records"),
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "random_seed": RANDOM_SEED,
    }
    (ANALYSIS / "analysis_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
