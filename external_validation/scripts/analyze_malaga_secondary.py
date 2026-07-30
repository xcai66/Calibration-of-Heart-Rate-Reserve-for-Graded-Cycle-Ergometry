from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"
RANDOM_SEED = 20260734
BOOTSTRAP_REPLICATES = 1000


def spearman(frame: pd.DataFrame, left: str, right: str) -> float:
    return float(frame[[left, right]].corr(method="spearman").iloc[0, 1])


def main() -> None:
    frame = pd.read_csv(PROCESSED / "malaga_external_test_metrics.csv", dtype={"participant": str})
    outcomes = {
        "epoc_180_ml": "180-s excess recovery VO2",
        "effort_peak_vo2_ml_min": "peak exercise VO2",
        "hr_recovery_60_bpm": "one-minute heart-rate recovery",
        "effort_peak_rer": "peak exercise RER",
        "recovery_peak_rer": "peak recovery RER",
    }
    exposures = ["mean_hrr", "thrr_i", "delta_tilt"]
    rng = np.random.default_rng(RANDOM_SEED)
    rows = []
    for outcome, label in outcomes.items():
        complete = frame.dropna(subset=exposures + [outcome]).copy()
        observed = {exposure: spearman(complete, exposure, outcome) for exposure in exposures}
        bootstrap = {exposure: [] for exposure in exposures}
        bootstrap["thrr_i_minus_mean_hrr"] = []
        eligible = np.array(sorted(complete["participant"].unique()), dtype=object)
        eligible_groups = {
            participant: np.asarray(indices, dtype=int)
            for participant, indices in complete.groupby("participant").indices.items()
        }
        for _ in range(BOOTSTRAP_REPLICATES):
            sampled = rng.choice(eligible, len(eligible), replace=True)
            sample_indices = np.concatenate([eligible_groups[participant] for participant in sampled])
            sample = complete.iloc[sample_indices]
            values = {exposure: spearman(sample, exposure, outcome) for exposure in exposures}
            for exposure in exposures:
                bootstrap[exposure].append(values[exposure])
            bootstrap["thrr_i_minus_mean_hrr"].append(values["thrr_i"] - values["mean_hrr"])
        for exposure in exposures:
            rows.append({
                "outcome": outcome,
                "outcome_label": label,
                "association": exposure,
                "tests": len(complete),
                "participants": complete["participant"].nunique(),
                "spearman_rho": observed[exposure],
                "ci_low": float(np.percentile(bootstrap[exposure], 2.5)),
                "ci_high": float(np.percentile(bootstrap[exposure], 97.5)),
            })
        rows.append({
            "outcome": outcome,
            "outcome_label": label,
            "association": "thrr_i_minus_mean_hrr",
            "tests": len(complete),
            "participants": complete["participant"].nunique(),
            "spearman_rho": observed["thrr_i"] - observed["mean_hrr"],
            "ci_low": float(np.percentile(bootstrap["thrr_i_minus_mean_hrr"], 2.5)),
            "ci_high": float(np.percentile(bootstrap["thrr_i_minus_mean_hrr"], 97.5)),
        })
    result = pd.DataFrame(rows)
    result.to_csv(RESULTS / "malaga_secondary_rank_associations.csv", index=False)
    summary = {
        "status": "exploratory_secondary",
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "participant_clustered": True,
        "all_prespecified_secondary_outcomes_reported": True,
        "results": result.to_dict("records"),
    }
    (RESULTS / "malaga_secondary_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
