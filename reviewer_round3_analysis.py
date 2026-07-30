from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_whr_as_public_data import fit_weighted_line, predict_weighted_line, spearman_rho
from assess_pmdata_matching import candidate_pairs, greedy_unique_match
from build_pmdata_session_dataset import (
    GAP_CAP_SECONDS,
    MIN_COVERAGE,
    MIN_VALID_MINUTES,
    collect_samples,
    load_daily_resting_heart_rate,
    load_participant_overview,
    participant_anchors,
    summarize_session,
)
from reviewer_round2_analysis import LAMBDA_GRID, binned_tilt, select_lambda


ROOT = Path(__file__).resolve().parent
ANALYSIS = ROOT / "analysis"
RANDOM_SEED = 20260730
BOOTSTRAP_REPLICATES = 5000
MIN_SESSIONS = 5


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    order = np.argsort(values)
    sorted_values = values[order]
    sorted_weights = weights[order]
    cumulative = np.cumsum(sorted_weights)
    if cumulative[-1] <= 0:
        return float("nan")
    return float(np.interp(quantile * cumulative[-1], cumulative, sorted_values))


def _raw_variant_summary(
    samples,
    duration_min: float,
    anchors: dict,
    *,
    gap_cap_seconds: float = GAP_CAP_SECONDS,
    confidence_minimum: int = 2,
    upper_winsor_fraction: float = 0.0,
    hrr_upper_cap: float = 1.0,
    hrmax_offset: float = 0.0,
    hrrest_offset: float = 0.0,
    force_tanaka_hrmax: bool = False,
) -> dict:
    if not samples.timestamps:
        return {"hr_qc_primary": False}
    timestamps = np.asarray([value.timestamp() for value in samples.timestamps], dtype=float)
    bpm = np.asarray(samples.bpm, dtype=float)
    confidence = np.asarray(samples.confidence, dtype=int)
    order = np.argsort(timestamps)
    timestamps, bpm, confidence = timestamps[order], bpm[order], confidence[order]
    unique = np.r_[True, np.diff(timestamps) > 0]
    timestamps, bpm, confidence = timestamps[unique], bpm[unique], confidence[unique]

    intervals = np.diff(timestamps, append=np.nan)
    positive = intervals[np.isfinite(intervals) & (intervals > 0) & (intervals <= gap_cap_seconds)]
    terminal = float(np.median(positive)) if len(positive) else 5.0
    intervals[-1] = min(terminal, gap_cap_seconds)
    valid = (bpm >= 30) & (bpm <= 220) & (confidence >= confidence_minimum)
    continuous = (intervals > 0) & (intervals <= gap_cap_seconds)
    weights = np.where(valid & continuous, intervals, 0.0)
    keep = weights > 0
    valid_seconds = float(weights.sum())
    coverage = min(valid_seconds / max(duration_min * 60.0, 1.0), 1.0)
    if valid_seconds <= 0:
        return {"hr_qc_primary": False, "hr_coverage": coverage, "valid_hr_minutes": 0.0}

    valid_bpm = bpm[keep].copy()
    valid_weights = weights[keep]
    if upper_winsor_fraction > 0:
        cutoff = _weighted_quantile(valid_bpm, valid_weights, 1.0 - upper_winsor_fraction)
        valid_bpm = np.minimum(valid_bpm, cutoff)

    hrrest = float(anchors["hrrest"]) + hrrest_offset
    if force_tanaka_hrmax:
        hrmax = 208.0 - 0.7 * float(anchors["age"])
    else:
        hrmax = float(anchors["hrmax"]) + hrmax_offset
    anchor_valid = math.isfinite(hrrest) and math.isfinite(hrmax) and hrmax > hrrest + 20
    if not anchor_valid:
        return {"hr_qc_primary": False, "hr_coverage": coverage, "valid_hr_minutes": valid_seconds / 60.0}

    hrr_unclipped = (valid_bpm - hrrest) / (hrmax - hrrest)
    hrr = np.clip(hrr_unclipped, 0.0, hrr_upper_cap)
    bins = np.minimum((hrr * 10).astype(int), 9)
    seconds = np.asarray([valid_weights[bins == index].sum() for index in range(10)], dtype=float)
    proportions = seconds / seconds.sum()
    return {
        "hr_qc_primary": bool(coverage >= MIN_COVERAGE and valid_seconds / 60.0 >= MIN_VALID_MINUTES),
        "hr_coverage": coverage,
        "valid_hr_minutes": valid_seconds / 60.0,
        "mean_hrr": float(np.average(hrr, weights=valid_weights)),
        "linear_score": float(np.dot(proportions, np.arange(1, 11))),
        "hrr_below_zero_fraction": float(valid_weights[hrr_unclipped < 0].sum() / valid_seconds),
        "hrr_above_one_fraction": float(valid_weights[hrr_unclipped > 1].sum() / valid_seconds),
        **{f"p{index}": float(proportions[index - 1]) for index in range(1, 11)},
    }


def _nested_compare(frame: pd.DataFrame, rng: np.random.Generator) -> dict:
    folds = []
    parameter_rows = []
    for held_out in sorted(frame["participant"].astype(str).unique()):
        train = frame[frame["participant"].astype(str) != held_out].copy()
        test = frame[frame["participant"].astype(str) == held_out].copy()
        lam = select_lambda(train, "ten_bins")
        train_tilted = binned_tilt(train, 10, lam)
        test_tilted = binned_tilt(test, 10, lam)
        train_linear = train["linear_score"].to_numpy(dtype=float)
        test_linear = test["linear_score"].to_numpy(dtype=float)
        tilted_model = fit_weighted_line(train_tilted, train["rpe"].to_numpy(), train["participant"].to_numpy())
        linear_model = fit_weighted_line(train_linear, train["rpe"].to_numpy(), train["participant"].to_numpy())
        fold = test[["participant", "rpe"]].copy()
        fold["score_tilted"] = test_tilted
        fold["score_linear"] = test_linear
        fold["pred_tilted"] = predict_weighted_line(tilted_model, test_tilted)
        fold["pred_linear"] = predict_weighted_line(linear_model, test_linear)
        folds.append(fold)
        parameter_rows.append(lam)
    predictions = pd.concat(folds, ignore_index=True)

    rows = []
    rho_tilted, rho_linear = [], []
    for participant, group in predictions.groupby("participant"):
        mae_tilted = float(np.mean(np.abs(group["pred_tilted"] - group["rpe"])))
        mae_linear = float(np.mean(np.abs(group["pred_linear"] - group["rpe"])))
        rows.append((str(participant), mae_tilted, mae_linear, mae_tilted - mae_linear))
        if len(group) >= MIN_SESSIONS:
            rt = spearman_rho(group["score_tilted"].to_numpy(), group["rpe"].to_numpy())
            rl = spearman_rho(group["score_linear"].to_numpy(), group["rpe"].to_numpy())
            if np.isfinite(rt) and np.isfinite(rl):
                rho_tilted.append(float(rt))
                rho_linear.append(float(rl))
    participant_table = pd.DataFrame(rows, columns=["participant", "mae_tilted", "mae_linear", "mae_difference"])
    differences = participant_table["mae_difference"].to_numpy(dtype=float)
    boot = np.asarray([
        rng.choice(differences, len(differences), replace=True).mean()
        for _ in range(BOOTSTRAP_REPLICATES)
    ])
    return {
        "sessions": int(len(frame)),
        "participants": int(frame["participant"].nunique()),
        "full_data_lambda": float(select_lambda(frame, "ten_bins")),
        "outer_lambda_median": float(np.median(parameter_rows)),
        "outer_lambda_q1": float(np.quantile(parameter_rows, 0.25)),
        "outer_lambda_q3": float(np.quantile(parameter_rows, 0.75)),
        "participant_balanced_mae_tilted": float(participant_table["mae_tilted"].mean()),
        "participant_balanced_mae_linear": float(participant_table["mae_linear"].mean()),
        "mae_difference_tilted_minus_linear": float(differences.mean()),
        "conditional_ci_low": float(np.percentile(boot, 2.5)),
        "conditional_ci_high": float(np.percentile(boot, 97.5)),
        "participants_with_rho": int(len(rho_tilted)),
        "median_within_participant_rho_tilted": float(np.median(rho_tilted)) if rho_tilted else float("nan"),
        "median_within_participant_rho_linear": float(np.median(rho_linear)) if rho_linear else float("nan"),
    }


def build_raw_robustness_frames(primary: pd.DataFrame) -> dict[str, pd.DataFrame]:
    output_columns = [
        "participant", "session_number", "rpe", "hr_qc_primary", "hr_coverage",
        "valid_hr_minutes", "mean_hrr", "linear_score", "hrr_below_zero_fraction",
        "hrr_above_one_fraction", *[f"p{index}" for index in range(1, 11)],
    ]
    overview = load_participant_overview()
    variants = {
        "baseline_rebuilt": {},
        "upper_0.5pct_bpm_winsorized": {"upper_winsor_fraction": 0.005},
        "upper_1pct_bpm_winsorized": {"upper_winsor_fraction": 0.01},
        "hrr_capped_at_0.95": {"hrr_upper_cap": 0.95},
        "gap_cap_15_seconds": {"gap_cap_seconds": 15.0},
        "confidence_3_only": {"confidence_minimum": 3},
        "hrmax_plus_5_bpm": {"hrmax_offset": 5.0},
        "hrmax_minus_5_bpm": {"hrmax_offset": -5.0},
        "hrrest_plus_3_bpm": {"hrrest_offset": 3.0},
        "hrrest_minus_3_bpm": {"hrrest_offset": -3.0},
        "tanaka_hrmax_for_all": {"force_tanaka_hrmax": True},
    }
    output = {name: [] for name in variants}
    for participant, group in primary.groupby("participant"):
        ordered = group.sort_values("exercise_start_local").copy()
        samples = collect_samples(str(participant), ordered)
        anchors = participant_anchors(str(participant), overview)
        for record, session_samples in zip(ordered.to_dict("records"), samples):
            base = {
                "participant": str(participant),
                "session_number": int(record["session_number"]),
                "rpe": float(record["rpe"]),
            }
            for name, options in variants.items():
                summary = _raw_variant_summary(
                    session_samples,
                    float(record["exercise_duration_min"]),
                    anchors,
                    **options,
                )
                if summary.get("hr_qc_primary", False):
                    output[name].append({**base, **summary})
    return {name: pd.DataFrame(rows, columns=output_columns) for name, rows in output.items()}


def _alternative_rule_matches(participants: list[str], rule: tuple) -> pd.DataFrame:
    name, low, high, duration_limit, cost_rule = rule
    rows = []
    for participant in participants:
        candidates = candidate_pairs(participant)
        if candidates.empty:
            continue
        candidates = candidates[candidates["report_delay_min"].between(low, high)].copy()
        if duration_limit is not None:
            candidates = candidates[candidates["duration_difference_min"] <= duration_limit].copy()
        if candidates.empty:
            continue
        if cost_rule == "delay":
            candidates["cost"] = candidates["report_delay_min"].abs()
        elif cost_rule == "duration":
            candidates["cost"] = candidates["duration_difference_min"] / np.maximum(candidates["rpe_duration_min"], 10.0)
        rpe_counts = candidates.groupby("rpe_index").size()
        exercise_counts = candidates.groupby("exercise_index").size()
        selected = greedy_unique_match(candidates)
        selected["participant"] = participant
        selected["match_unique_both_directions"] = [
            bool(rpe_counts.loc[int(row.rpe_index)] == 1 and exercise_counts.loc[int(row.exercise_index)] == 1)
            for row in selected.itertuples()
        ]
        rows.append(selected[selected["match_unique_both_directions"]].copy())
    result = pd.concat(rows, ignore_index=True)
    result["matching_rule"] = name
    return result


def build_alternative_matching_frames(qc: pd.DataFrame) -> dict[str, pd.DataFrame]:
    rules = [
        ("delay_15_90_min", 15.0, 90.0, None, "default"),
        ("delay_30_120_min", 30.0, 120.0, None, "default"),
        ("duration_difference_le_10_min", 15.0, 180.0, 10.0, "default"),
        ("delay_priority_cost", 15.0, 180.0, None, "delay"),
        ("duration_priority_cost", 15.0, 180.0, None, "duration"),
    ]
    participants = sorted(qc["participant"].astype(str).unique())
    metric_columns = [
        "participant", "exercise_index", "hr_qc_primary", "valid_hr_minutes", "hr_coverage",
        "mean_hrr", "linear_score", *[f"p{i}" for i in range(1, 11)],
    ]
    metric_table = qc[metric_columns].drop_duplicates(["participant", "exercise_index"])
    overview = load_participant_overview()
    output = {}
    for rule in rules:
        selected = _alternative_rule_matches(participants, rule)
        frame = selected.merge(metric_table, on=["participant", "exercise_index"], how="left")
        missing = frame[frame["hr_qc_primary"].isna()].copy()
        if not missing.empty:
            replacements = []
            for participant, group in missing.groupby("participant"):
                ordered = group.sort_values("exercise_start_local").copy()
                samples = collect_samples(str(participant), ordered)
                anchors = participant_anchors(str(participant), overview)
                daily = load_daily_resting_heart_rate(str(participant))
                for record, sample in zip(ordered.to_dict("records"), samples):
                    summary = summarize_session(
                        sample,
                        float(record["exercise_duration_min"]),
                        anchors,
                        pd.Timestamp(record["exercise_start_local"]).to_pydatetime(),
                        daily,
                    )
                    replacements.append({"participant": str(participant), "exercise_index": int(record["exercise_index"]), **summary})
            replacement_table = pd.DataFrame(replacements)
            if not replacement_table.empty:
                frame = frame.drop(columns=[column for column in metric_columns if column not in {"participant", "exercise_index"}])
                expanded_metrics = pd.concat([metric_table, replacement_table[metric_columns]], ignore_index=True).drop_duplicates(
                    ["participant", "exercise_index"], keep="last"
                )
                frame = selected.merge(expanded_metrics, on=["participant", "exercise_index"], how="left")
        rpe_numeric = pd.to_numeric(frame["rpe"], errors="coerce")
        frame = frame[(rpe_numeric >= 1) & (rpe_numeric <= 10) & frame["hr_qc_primary"].fillna(False).astype(bool)].copy()
        frame["rpe"] = pd.to_numeric(frame["rpe"], errors="coerce")
        frame["session_number"] = frame["exercise_index"].astype(int)
        output[str(rule[0])] = frame
    return output


def main() -> None:
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RANDOM_SEED)
    primary = pd.read_csv(ANALYSIS / "pmdata_primary_analysis_sessions.csv")
    qc = pd.read_csv(ANALYSIS / "pmdata_session_level_qc.csv")

    robustness_frames = build_raw_robustness_frames(primary)
    robustness_rows = []
    for variant, frame in robustness_frames.items():
        if frame.empty or "participant" not in frame.columns:
            result = {
                "sessions": 0,
                "participants": 0,
                "full_data_lambda": float("nan"),
                "outer_lambda_median": float("nan"),
                "outer_lambda_q1": float("nan"),
                "outer_lambda_q3": float("nan"),
                "participant_balanced_mae_tilted": float("nan"),
                "participant_balanced_mae_linear": float("nan"),
                "mae_difference_tilted_minus_linear": float("nan"),
                "conditional_ci_low": float("nan"),
                "conditional_ci_high": float("nan"),
                "participants_with_rho": 0,
                "median_within_participant_rho_tilted": float("nan"),
                "median_within_participant_rho_linear": float("nan"),
            }
        else:
            result = _nested_compare(frame, rng)
        result["variant"] = variant
        robustness_rows.append(result)
        frame.to_csv(ANALYSIS / f"reviewer_round3_sessions_{variant}.csv", index=False)
    robustness = pd.DataFrame(robustness_rows)

    baseline = robustness_frames["baseline_rebuilt"]
    archived = primary[["participant", "session_number", *[f"p{i}" for i in range(1, 11)]]].copy()
    merged = archived.merge(baseline, on=["participant", "session_number"], suffixes=("_archived", "_rebuilt"))
    differences = []
    for index in range(1, 11):
        differences.append(np.abs(merged[f"p{index}_archived"] - merged[f"p{index}_rebuilt"]).to_numpy())
    reconstruction_max_abs = float(np.max(np.concatenate(differences)))

    matching_frames = build_alternative_matching_frames(qc)
    matching_rows = []
    for rule, frame in matching_frames.items():
        result = _nested_compare(frame, rng)
        result["matching_rule"] = rule
        matching_rows.append(result)
        frame.to_csv(ANALYSIS / f"reviewer_round3_matching_sessions_{rule}.csv", index=False)
    matching_performance = pd.DataFrame(matching_rows)

    full_lambda = float(robustness.loc[robustness["variant"] == "baseline_rebuilt", "full_data_lambda"].iloc[0])
    weight_profile = pd.DataFrame([
        {
            "full_data_lambda": full_lambda,
            "adjacent_decile_multiplier": float(np.exp(full_lambda / 10.0)),
            "weight_ratio_0.95_vs_0.05": float(np.exp(full_lambda * 0.90)),
            "interpretation": "Relative exponential weight before normalization; the final index remains bounded in [0,1].",
        }
    ])

    robustness.to_csv(ANALYSIS / "reviewer_round3_raw_signal_and_anchor_sensitivity.csv", index=False)
    matching_performance.to_csv(ANALYSIS / "reviewer_round3_matching_model_performance.csv", index=False)
    weight_profile.to_csv(ANALYSIS / "reviewer_round3_weight_profile.csv", index=False)
    payload = {
        "raw_signal_and_anchor_sensitivity": robustness.to_dict("records"),
        "alternative_matching_model_performance": matching_performance.to_dict("records"),
        "weight_profile": weight_profile.to_dict("records"),
        "reconstruction_max_absolute_bin_difference": reconstruction_max_abs,
        "uncertainty_note": "Intervals are participant-cluster bootstrap intervals conditional on the realized nested predictions and the chosen formula family.",
        "random_seed": RANDOM_SEED,
    }
    (ANALYSIS / "reviewer_round3_analysis.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
