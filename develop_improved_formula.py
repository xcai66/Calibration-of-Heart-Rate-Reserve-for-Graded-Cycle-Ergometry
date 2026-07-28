from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_whr_as_public_data import (
    BOOTSTRAP_REPLICATES,
    RANDOM_SEED,
    fit_weighted_line,
    predict_weighted_line,
    spearman_rho,
)


ROOT = Path(__file__).resolve().parent
ANALYSIS = ROOT / "analysis"
MIN_SESSIONS = 5
CENTERS = (np.arange(1, 11, dtype=float) - 0.5) / 10.0


FAMILIES = {
    "original_exp": np.round(np.arange(0.01, 1.501, 0.01), 2),
    "entropic_hrr": np.round(np.arange(0.0, 15.01, 0.1), 1),
    "tilted_hrr": np.round(np.arange(0.0, 15.01, 0.1), 1),
    "power_hrr": np.round(np.arange(1.0, 12.01, 0.1), 1),
}


def proportions(frame: pd.DataFrame) -> np.ndarray:
    return frame[[f"p{i}" for i in range(1, 11)]].to_numpy(dtype=float)


def score_family(frame: pd.DataFrame, family: str, parameter: float | None = None) -> np.ndarray:
    p = proportions(frame)
    if family == "linear_decile":
        return p @ np.arange(1, 11, dtype=float)
    if family == "mean_hrr":
        return frame["mean_hrr"].to_numpy(dtype=float)
    if family == "banister_trimp":
        return frame["banister_trimp_integral"].to_numpy(dtype=float)
    if parameter is None:
        raise ValueError(f"{family} requires a parameter")
    if family == "original_exp":
        return p @ np.exp(float(parameter) * np.arange(1, 11, dtype=float))
    if family == "entropic_hrr":
        lam = float(parameter)
        if abs(lam) < 1e-12:
            return p @ CENTERS
        return np.log(p @ np.exp(lam * CENTERS)) / lam
    if family == "tilted_hrr":
        lam = float(parameter)
        weights = np.exp(lam * CENTERS)
        return (p @ (CENTERS * weights)) / (p @ weights)
    if family == "power_hrr":
        q = float(parameter)
        return np.power(p @ np.power(CENTERS, q), 1.0 / q)
    raise KeyError(family)


def participant_correlations(frame: pd.DataFrame, values: np.ndarray, outcome: str = "rpe") -> dict[str, float]:
    working = frame[["participant", outcome]].copy()
    working["score"] = values
    output: dict[str, float] = {}
    for participant, group in working.groupby("participant"):
        if len(group) < MIN_SESSIONS:
            continue
        rho = spearman_rho(group["score"].to_numpy(), group[outcome].to_numpy())
        if math.isfinite(rho):
            output[str(participant)] = rho
    return output


def select_parameter(frame: pd.DataFrame, family: str) -> tuple[float, pd.DataFrame]:
    rows = []
    for parameter in FAMILIES[family]:
        correlations = participant_correlations(frame, score_family(frame, family, float(parameter)))
        rows.append(
            {
                "family": family,
                "parameter": float(parameter),
                "participants": len(correlations),
                "median_participant_rho": float(np.median(list(correlations.values())))
                if correlations
                else float("nan"),
            }
        )
    profile = pd.DataFrame(rows)
    valid = profile.dropna(subset=["median_participant_rho"])
    maximum = valid["median_participant_rho"].max()
    selected = float(valid.loc[np.isclose(valid["median_participant_rho"], maximum), "parameter"].min())
    return selected, profile


def nested_predictions(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidates = list(FAMILIES) + ["linear_decile", "mean_hrr", "banister_trimp"]
    fold_outputs = []
    parameter_rows = []
    for held_out in sorted(frame["participant"].unique()):
        train = frame[frame["participant"] != held_out].copy()
        test = frame[frame["participant"] == held_out].copy()
        selected = {}
        for family in FAMILIES:
            selected[family], _ = select_parameter(train, family)
            parameter_rows.append(
                {
                    "held_out_participant": held_out,
                    "family": family,
                    "selected_parameter": selected[family],
                    "training_participants": train["participant"].nunique(),
                    "training_sessions": len(train),
                    "test_sessions": len(test),
                }
            )
        fold = test[
            [
                "participant",
                "session_number",
                "exercise_start_local",
                "exercise_name",
                "rpe",
                "rpe_duration_min",
                "exercise_duration_min",
                "srpe_load",
            ]
        ].copy()
        for family in candidates:
            parameter = selected.get(family)
            train_score = score_family(train, family, parameter)
            test_score = score_family(test, family, parameter)
            model = fit_weighted_line(train_score, train["rpe"].to_numpy(), train["participant"].to_numpy())
            fold[f"score_{family}"] = test_score
            fold[f"pred_{family}"] = predict_weighted_line(model, test_score)
            if family == "banister_trimp":
                train_load_score = train_score
                test_load_score = test_score
            else:
                train_load_score = train_score * train["exercise_duration_min"].to_numpy(dtype=float)
                test_load_score = test_score * test["exercise_duration_min"].to_numpy(dtype=float)
            load_model = fit_weighted_line(
                np.log1p(np.maximum(train_load_score, 0.0)),
                np.log1p(train["srpe_load"].to_numpy(dtype=float)),
                train["participant"].to_numpy(),
            )
            predicted_log_load = predict_weighted_line(load_model, np.log1p(np.maximum(test_load_score, 0.0)))
            fold[f"load_score_{family}"] = test_load_score
            fold[f"pred_log_load_{family}"] = predicted_log_load
        fold_outputs.append(fold)
    return pd.concat(fold_outputs, ignore_index=True), pd.DataFrame(parameter_rows)


def association_table(predictions: pd.DataFrame, outcome: str, prefix: str) -> pd.DataFrame:
    families = list(FAMILIES) + ["linear_decile", "mean_hrr", "banister_trimp"]
    rows = []
    for participant, group in predictions.groupby("participant"):
        if len(group) < MIN_SESSIONS:
            continue
        row = {"participant": participant, "sessions": len(group)}
        for family in families:
            row[family] = spearman_rho(group[f"{prefix}{family}"].to_numpy(), group[outcome].to_numpy())
        rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_median_and_differences(table: pd.DataFrame, reference: str, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    families = [c for c in table.columns if c not in {"participant", "sessions"}]
    summary = []
    comparisons = []
    n = len(table)
    for family in families:
        values = table[family].to_numpy(dtype=float)
        boot = np.array([np.median(rng.choice(values, n, replace=True)) for _ in range(BOOTSTRAP_REPLICATES)])
        summary.append(
            {
                "family": family,
                "participants": n,
                "median_participant_rho": float(np.median(values)),
                "ci_low": float(np.percentile(boot, 2.5)),
                "ci_high": float(np.percentile(boot, 97.5)),
            }
        )
        if family != reference:
            diff = values - table[reference].to_numpy(dtype=float)
            diff_boot = np.array([np.median(rng.choice(diff, n, replace=True)) for _ in range(BOOTSTRAP_REPLICATES)])
            comparisons.append(
                {
                    "family": family,
                    "reference": reference,
                    "participants": n,
                    "median_paired_rho_difference": float(np.median(diff)),
                    "ci_low": float(np.percentile(diff_boot, 2.5)),
                    "ci_high": float(np.percentile(diff_boot, 97.5)),
                }
            )
    return pd.DataFrame(summary), pd.DataFrame(comparisons)


def prediction_performance(predictions: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    families = list(FAMILIES) + ["linear_decile", "mean_hrr", "banister_trimp"]
    groups = {participant: group for participant, group in predictions.groupby("participant")}
    participants = np.array(sorted(groups), dtype=object)

    def calculate(family: str, sampled: np.ndarray) -> tuple[float, float, float]:
        maes = []
        mses = []
        observed = []
        predicted = []
        for participant in sampled:
            group = groups[str(participant)]
            y = group["rpe"].to_numpy(dtype=float)
            pred = group[f"pred_{family}"].to_numpy(dtype=float)
            error = pred - y
            maes.append(float(np.mean(np.abs(error))))
            mses.append(float(np.mean(error**2)))
            observed.append(y)
            predicted.append(pred)
        y_all = np.concatenate(observed)
        pred_all = np.concatenate(predicted)
        denominator = float(np.sum((y_all - np.mean(y_all)) ** 2))
        r2 = 1.0 - float(np.sum((y_all - pred_all) ** 2)) / denominator if denominator > 0 else float("nan")
        return float(np.mean(maes)), float(np.sqrt(np.mean(mses))), r2

    summary = []
    comparisons = []
    n = len(participants)
    for family in families:
        observed = calculate(family, participants)
        boot = np.empty((BOOTSTRAP_REPLICATES, 3), dtype=float)
        for index in range(BOOTSTRAP_REPLICATES):
            boot[index] = calculate(family, rng.choice(participants, n, replace=True))
        summary.append(
            {
                "family": family,
                "participants": n,
                "participant_balanced_mae": observed[0],
                "mae_ci_low": float(np.nanpercentile(boot[:, 0], 2.5)),
                "mae_ci_high": float(np.nanpercentile(boot[:, 0], 97.5)),
                "participant_balanced_rmse": observed[1],
                "rmse_ci_low": float(np.nanpercentile(boot[:, 1], 2.5)),
                "rmse_ci_high": float(np.nanpercentile(boot[:, 1], 97.5)),
                "pooled_cv_r2": observed[2],
                "r2_ci_low": float(np.nanpercentile(boot[:, 2], 2.5)),
                "r2_ci_high": float(np.nanpercentile(boot[:, 2], 97.5)),
            }
        )
    for reference in ["linear_decile", "original_exp"]:
        reference_participant_mae = np.array(
            [
                np.mean(
                    np.abs(
                        groups[str(participant)][f"pred_{reference}"].to_numpy(dtype=float)
                        - groups[str(participant)]["rpe"].to_numpy(dtype=float)
                    )
                )
                for participant in participants
            ]
        )
        for family in families:
            if family == reference:
                continue
            family_participant_mae = np.array(
                [
                    np.mean(
                        np.abs(
                            groups[str(participant)][f"pred_{family}"].to_numpy(dtype=float)
                            - groups[str(participant)]["rpe"].to_numpy(dtype=float)
                        )
                    )
                    for participant in participants
                ]
            )
            diff = family_participant_mae - reference_participant_mae
            diff_boot = np.array([np.mean(rng.choice(diff, n, replace=True)) for _ in range(BOOTSTRAP_REPLICATES)])
            comparisons.append(
                {
                    "family": family,
                    "reference": reference,
                    "participants": n,
                    "mae_difference": float(np.mean(diff)),
                    "ci_low": float(np.percentile(diff_boot, 2.5)),
                    "ci_high": float(np.percentile(diff_boot, 97.5)),
                }
            )
    return pd.DataFrame(summary), pd.DataFrame(comparisons)


def main() -> None:
    rng = np.random.default_rng(RANDOM_SEED + 1)
    primary = pd.read_csv(ANALYSIS / "pmdata_primary_analysis_sessions.csv")
    predictions, parameters = nested_predictions(primary)
    intensity = association_table(predictions, "rpe", "score_")
    load = association_table(predictions, "srpe_load", "load_score_")
    intensity_summary, intensity_comparisons = bootstrap_median_and_differences(
        intensity, "linear_decile", rng
    )
    load_summary, load_comparisons = bootstrap_median_and_differences(load, "linear_decile", rng)
    prediction_summary, prediction_comparisons = prediction_performance(predictions, rng)

    profile_outputs = []
    full_parameters = []
    for family in FAMILIES:
        selected, profile = select_parameter(primary, family)
        full_parameters.append({"family": family, "selected_parameter": selected})
        profile_outputs.append(profile)

    outputs = {
        "improved_formula_nested_predictions.csv": predictions,
        "improved_formula_outer_parameters.csv": parameters,
        "improved_formula_intensity_associations.csv": intensity,
        "improved_formula_intensity_summary.csv": intensity_summary,
        "improved_formula_intensity_comparisons.csv": intensity_comparisons,
        "improved_formula_load_associations.csv": load,
        "improved_formula_load_summary.csv": load_summary,
        "improved_formula_load_comparisons.csv": load_comparisons,
        "improved_formula_prediction_summary.csv": prediction_summary,
        "improved_formula_prediction_comparisons.csv": prediction_comparisons,
        "improved_formula_parameter_profiles.csv": pd.concat(profile_outputs, ignore_index=True),
        "improved_formula_full_parameters.csv": pd.DataFrame(full_parameters),
    }
    for name, table in outputs.items():
        table.to_csv(ANALYSIS / name, index=False)

    summary = {
        "formula_definitions": {
            "entropic_hrr": "log(sum_i P_i exp(lambda c_i))/lambda; limit at lambda=0 is sum_i P_i c_i",
            "tilted_hrr": "sum_i P_i c_i exp(lambda c_i) / sum_i P_i exp(lambda c_i)",
            "power_hrr": "(sum_i P_i c_i^q)^(1/q)",
            "centers": CENTERS.tolist(),
            "load_extension": "exercise duration in minutes multiplied by the corresponding intensity score",
        },
        "full_data_parameters": full_parameters,
        "outer_parameter_summary": parameters.groupby("family")["selected_parameter"].agg(
            median="median", q1=lambda x: x.quantile(0.25), q3=lambda x: x.quantile(0.75), minimum="min", maximum="max"
        ).reset_index().to_dict("records"),
        "intensity_association": intensity_summary.to_dict("records"),
        "intensity_comparisons": intensity_comparisons.to_dict("records"),
        "load_association": load_summary.to_dict("records"),
        "load_comparisons": load_comparisons.to_dict("records"),
        "prediction_performance": prediction_summary.to_dict("records"),
        "prediction_comparisons": prediction_comparisons.to_dict("records"),
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "random_seed": RANDOM_SEED + 1,
    }
    (ANALYSIS / "improved_formula_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
