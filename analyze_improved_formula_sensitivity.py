from __future__ import annotations

import json
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
from develop_improved_formula import score_family, select_parameter


ROOT = Path(__file__).resolve().parent
ANALYSIS = ROOT / "analysis"
MIN_SESSIONS = 5


def nested_tilted(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    folds = []
    parameter_rows = []
    for held_out in sorted(frame["participant"].unique()):
        train = frame[frame["participant"] != held_out].copy()
        test = frame[frame["participant"] == held_out].copy()
        parameter, _ = select_parameter(train, "tilted_hrr")
        train_tilted = score_family(train, "tilted_hrr", parameter)
        test_tilted = score_family(test, "tilted_hrr", parameter)
        train_linear = score_family(train, "linear_decile")
        test_linear = score_family(test, "linear_decile")
        folded = test[["participant", "session_number", "rpe"]].copy()
        folded["selected_lambda"] = parameter
        for name, train_values, test_values in [
            ("tilted_hrr", train_tilted, test_tilted),
            ("linear_decile", train_linear, test_linear),
        ]:
            model = fit_weighted_line(
                train_values,
                train["rpe"].to_numpy(dtype=float),
                train["participant"].to_numpy(),
            )
            folded[f"score_{name}"] = test_values
            folded[f"pred_{name}"] = predict_weighted_line(model, test_values)
        folds.append(folded)
        parameter_rows.append(
            {
                "held_out_participant": held_out,
                "selected_lambda": parameter,
                "training_sessions": len(train),
                "test_sessions": len(test),
            }
        )
    return pd.concat(folds, ignore_index=True), pd.DataFrame(parameter_rows)


def summarize(name: str, frame: pd.DataFrame, rng: np.random.Generator) -> dict:
    predictions, parameters = nested_tilted(frame)
    paired_rhos = []
    participant_mae = []
    for participant, group in predictions.groupby("participant"):
        error_tilted = np.mean(np.abs(group["pred_tilted_hrr"] - group["rpe"]))
        error_linear = np.mean(np.abs(group["pred_linear_decile"] - group["rpe"]))
        participant_mae.append((float(error_tilted), float(error_linear)))
        if len(group) >= MIN_SESSIONS:
            rho_tilted = spearman_rho(group["score_tilted_hrr"].to_numpy(), group["rpe"].to_numpy())
            rho_linear = spearman_rho(group["score_linear_decile"].to_numpy(), group["rpe"].to_numpy())
            paired_rhos.append((rho_tilted, rho_linear))

    rho_array = np.asarray(paired_rhos, dtype=float)
    mae_array = np.asarray(participant_mae, dtype=float)
    rho_diff = rho_array[:, 0] - rho_array[:, 1]
    mae_diff = mae_array[:, 0] - mae_array[:, 1]
    boot_rho = np.array(
        [np.median(rng.choice(rho_diff, len(rho_diff), replace=True)) for _ in range(BOOTSTRAP_REPLICATES)]
    )
    boot_mae = np.array(
        [np.mean(rng.choice(mae_diff, len(mae_diff), replace=True)) for _ in range(BOOTSTRAP_REPLICATES)]
    )
    return {
        "analysis": name,
        "sessions": len(frame),
        "participants": frame["participant"].nunique(),
        "participants_with_at_least_5_sessions": len(rho_array),
        "outer_lambda_median": float(parameters["selected_lambda"].median()),
        "outer_lambda_q1": float(parameters["selected_lambda"].quantile(0.25)),
        "outer_lambda_q3": float(parameters["selected_lambda"].quantile(0.75)),
        "tilted_median_participant_rho": float(np.median(rho_array[:, 0])),
        "linear_median_participant_rho": float(np.median(rho_array[:, 1])),
        "median_paired_rho_difference": float(np.median(rho_diff)),
        "rho_difference_ci_low": float(np.percentile(boot_rho, 2.5)),
        "rho_difference_ci_high": float(np.percentile(boot_rho, 97.5)),
        "tilted_participant_balanced_mae": float(np.mean(mae_array[:, 0])),
        "linear_participant_balanced_mae": float(np.mean(mae_array[:, 1])),
        "mae_difference": float(np.mean(mae_diff)),
        "mae_difference_ci_low": float(np.percentile(boot_mae, 2.5)),
        "mae_difference_ci_high": float(np.percentile(boot_mae, 97.5)),
    }


def main() -> None:
    rng = np.random.default_rng(RANDOM_SEED + 2)
    primary = pd.read_csv(ANALYSIS / "pmdata_primary_analysis_sessions.csv")
    analyses = {
        "primary": primary,
        "measured_hrmax_only": primary[primary["measured_hrmax_available"].astype(bool)].copy(),
        "exclude_sessions_with_gt5pct_hrr_above_one": primary[primary["hrr_above_one_fraction"] <= 0.05].copy(),
        "duration_difference_at_most_10_min": primary[primary["duration_difference_min"] <= 10].copy(),
        "run_or_treadmill_only": primary[primary["exercise_name"].isin(["Run", "Treadmill"])].copy(),
        "daily_resting_hr_source_only": primary[
            primary["hrrest_source"].eq("median Fitbit daily resting heart rate")
        ].copy(),
    }
    rows = [summarize(name, frame, rng) for name, frame in analyses.items()]
    table = pd.DataFrame(rows)
    table.to_csv(ANALYSIS / "improved_formula_sensitivity.csv", index=False)
    payload = {
        "analyses": rows,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "random_seed": RANDOM_SEED + 2,
    }
    (ANALYSIS / "improved_formula_sensitivity.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
