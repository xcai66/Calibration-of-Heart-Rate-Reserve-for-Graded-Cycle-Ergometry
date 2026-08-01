from __future__ import annotations

"""Repeated-measures WEEE agreement and stage-flow audit.

Measurement occasions are nested within participants.  The primary agreement
summary therefore uses participant-balanced concordance and variance-component
limits of agreement.  The original stage-level ICC(A,1), with participant-
cluster bootstrap intervals, remains available as a secondary descriptor in the
round-4 outputs.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
RESULTS = ROOT / "results"
RANDOM_SEED = 20260801
BOOTSTRAP_REPLICATES = 5000
STAGES = ["sit", "stand", "cycle_low", "cycle_high", "run_low", "run_high"]


def participant_balanced_weights(frame: pd.DataFrame) -> np.ndarray:
    counts = frame["participant"].astype(str).value_counts()
    weight = frame["participant"].astype(str).map(lambda value: 1.0 / counts[value]).to_numpy(dtype=float)
    return weight / weight.sum()


def weighted_ccc(left: np.ndarray, right: np.ndarray, weight: np.ndarray) -> float:
    mean_left = float(np.sum(weight * left))
    mean_right = float(np.sum(weight * right))
    centered_left = left - mean_left
    centered_right = right - mean_right
    variance_left = float(np.sum(weight * centered_left**2))
    variance_right = float(np.sum(weight * centered_right**2))
    covariance = float(np.sum(weight * centered_left * centered_right))
    denominator = variance_left + variance_right + (mean_left - mean_right) ** 2
    return float(2.0 * covariance / denominator) if denominator > 0 else np.nan


def repeated_measure_summary(frame: pd.DataFrame, metric: str) -> dict[str, float]:
    working = frame[["participant", f"reference_{metric}", f"device_{metric}"]].dropna().copy()
    working["difference"] = working[f"device_{metric}"] - working[f"reference_{metric}"]
    groups = list(working.groupby("participant", sort=True))
    participant_means = np.asarray([group["difference"].mean() for _, group in groups], dtype=float)
    participant_sizes = np.asarray([len(group) for _, group in groups], dtype=float)
    n_total = int(participant_sizes.sum())
    n_participants = len(groups)

    grand = float(working["difference"].mean())
    ss_between = float(sum(len(group) * (group["difference"].mean() - grand) ** 2 for _, group in groups))
    ss_within = float(sum(((group["difference"] - group["difference"].mean()) ** 2).sum() for _, group in groups))
    ms_between = ss_between / (n_participants - 1) if n_participants > 1 else np.nan
    ms_within = ss_within / (n_total - n_participants) if n_total > n_participants else np.nan
    effective_repeats = (
        (n_total - float(np.sum(participant_sizes**2)) / n_total) / (n_participants - 1)
        if n_participants > 1 else np.nan
    )
    between_variance = max((ms_between - ms_within) / effective_repeats, 0.0)
    within_variance = max(ms_within, 0.0)
    total_sd = float(np.sqrt(between_variance + within_variance))
    bias = float(participant_means.mean())

    weight = participant_balanced_weights(working)
    reference = working[f"reference_{metric}"].to_numpy(dtype=float)
    device = working[f"device_{metric}"].to_numpy(dtype=float)
    reference_centered = working[f"reference_{metric}"] - working.groupby("participant")[f"reference_{metric}"].transform("mean")
    device_centered = working[f"device_{metric}"] - working.groupby("participant")[f"device_{metric}"].transform("mean")
    centered_denominator = float(np.sqrt(np.sum(weight * reference_centered**2) * np.sum(weight * device_centered**2)))
    centered_r = (
        float(np.sum(weight * reference_centered * device_centered) / centered_denominator)
        if centered_denominator > 0 else np.nan
    )
    return {
        "participants": n_participants,
        "stages": n_total,
        "participant_balanced_bias": bias,
        "between_participant_difference_variance": float(between_variance),
        "within_participant_difference_variance": float(within_variance),
        "repeated_measures_loa_lower": float(bias - 1.96 * total_sd),
        "repeated_measures_loa_upper": float(bias + 1.96 * total_sd),
        "participant_balanced_ccc": weighted_ccc(reference, device, weight),
        "participant_centered_pearson_r": centered_r,
    }


def bootstrap_summary(frame: pd.DataFrame, metric: str, rng: np.random.Generator) -> dict[str, float]:
    participants = np.asarray(sorted(frame["participant"].astype(str).unique()), dtype=object)
    groups = {participant: group.copy() for participant, group in frame.groupby(frame["participant"].astype(str))}
    keys = [
        "participant_balanced_bias", "repeated_measures_loa_lower",
        "repeated_measures_loa_upper", "participant_balanced_ccc",
        "participant_centered_pearson_r",
    ]
    boot = {key: [] for key in keys}
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled = rng.choice(participants, len(participants), replace=True)
        copies = []
        for copy_index, participant in enumerate(sampled):
            group = groups[str(participant)].copy()
            group["participant"] = f"{participant}__{copy_index}"
            copies.append(group)
        summary = repeated_measure_summary(pd.concat(copies, ignore_index=True), metric)
        for key in keys:
            boot[key].append(summary[key])
    output = {}
    for key in keys:
        values = np.asarray(boot[key], dtype=float)
        output[f"{key}_ci_low"] = float(np.nanpercentile(values, 2.5))
        output[f"{key}_ci_high"] = float(np.nanpercentile(values, 97.5))
    return output


def stage_flow(construct: pd.DataFrame, exclusions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # The source contains 17 participants. P10 lacked the sitting anchor, so all
    # six stages were excluded before stage-level signal quality control.
    participant_flow = pd.DataFrame([
        ("Source participants", 17, 102, "17 participants x 6 protocol stages"),
        ("Participants with resting-HR anchor", 16, 96, "P10 excluded because the sitting anchor was missing"),
        ("Final construct-analysis sample", 16, len(construct), "19 additional participant-stage records failed reference HR or VO2 coverage"),
    ], columns=["flow_stage", "participants", "participant_stages", "reason"])

    rows = []
    for stage in STAGES:
        included = int((construct["stage"] == stage).sum())
        excluded = int(((exclusions["stage"] == stage) & exclusions["stage"].notna()).sum())
        rows.append({
            "stage": stage,
            "eligible_after_anchor_qc": 16,
            "included": included,
            "excluded_stage_qc": excluded,
            "retention_percent": 100.0 * included / 16.0,
        })
    return participant_flow, pd.DataFrame(rows)


def main() -> None:
    pairs = pd.read_csv(DATA / "weee_device_stage_pairs.csv")
    construct = pd.read_csv(DATA / "weee_construct_stage_metrics.csv")
    exclusions = pd.read_csv(RESULTS / "weee_qc_exclusions.csv")
    rng = np.random.default_rng(RANDOM_SEED)
    rows = []
    for device in sorted(pairs["device"].unique()):
        subset = pairs[pairs["device"] == device].copy()
        for metric in ["mean_hrr", "thrr_i", "delta_tilt"]:
            observed = repeated_measure_summary(subset, metric)
            intervals = bootstrap_summary(subset, metric, rng)
            rows.append({"device": device, "score": metric, **observed, **intervals})
    agreement = pd.DataFrame(rows)
    participant_flow, stage_table = stage_flow(construct, exclusions)
    agreement.to_csv(RESULTS / "reviewer_round5_weee_repeated_agreement.csv", index=False)
    participant_flow.to_csv(RESULTS / "reviewer_round5_weee_participant_flow.csv", index=False)
    stage_table.to_csv(RESULTS / "reviewer_round5_weee_stage_flow.csv", index=False)
    payload = {
        "agreement": agreement.to_dict("records"),
        "participant_flow": participant_flow.to_dict("records"),
        "stage_flow": stage_table.to_dict("records"),
        "method_note": (
            "Bias is participant balanced. Limits of agreement use the sum of between- and "
            "within-participant difference variance components. Concordance uses equal total "
            "weight per participant. Intervals resample participants with replacement."
        ),
        "random_seed": RANDOM_SEED,
    }
    (RESULTS / "reviewer_round5_weee_agreement.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
