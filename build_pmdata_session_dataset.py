from __future__ import annotations

import bisect
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from assess_pmdata_matching import BASE, candidate_pairs, greedy_unique_match


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "analysis"
OSLO = ZoneInfo("Europe/Oslo")
GAP_CAP_SECONDS = 30.0
MIN_COVERAGE = 0.80
MIN_VALID_MINUTES = 10.0
LAMBDA_GRID = np.round(np.arange(0.0, 15.01, 0.1), 1)


@dataclass
class SessionSamples:
    timestamps: list[datetime] = field(default_factory=list)
    bpm: list[int] = field(default_factory=list)
    confidence: list[int] = field(default_factory=list)


def iter_json_array(path: Path, chunk_size: int = 1024 * 1024) -> Iterator[dict]:
    decoder = json.JSONDecoder()
    with path.open("r", encoding="utf-8") as handle:
        buffer = ""
        position = 0
        started = False
        exhausted = False
        while True:
            if position >= len(buffer) - 1024 and not exhausted:
                buffer = buffer[position:] + handle.read(chunk_size)
                position = 0
                if len(buffer) < chunk_size:
                    exhausted = True
            while position < len(buffer) and buffer[position].isspace():
                position += 1
            if not started:
                if position >= len(buffer):
                    break
                if buffer[position] != "[":
                    raise ValueError(f"Expected JSON array in {path}")
                started = True
                position += 1
                continue
            while position < len(buffer) and (buffer[position].isspace() or buffer[position] == ","):
                position += 1
            if position < len(buffer) and buffer[position] == "]":
                break
            try:
                item, next_position = decoder.raw_decode(buffer, position)
                position = next_position
                yield item
            except json.JSONDecodeError:
                if exhausted:
                    raise
                buffer = buffer[position:] + handle.read(chunk_size)
                position = 0


def load_participant_overview() -> pd.DataFrame:
    path = BASE / "participant-overview.xlsx"
    frame = pd.read_excel(path, header=1)
    frame = frame.rename(
        columns={
            "Participant ID": "participant",
            "Age": "age",
            "Height": "height_cm",
            "Gender": "sex",
            "Max heart rate": "measured_hrmax",
        }
    )
    frame["participant"] = frame["participant"].astype(str).str.strip()
    frame["age"] = pd.to_numeric(frame["age"], errors="coerce")
    frame["measured_hrmax"] = pd.to_numeric(frame["measured_hrmax"], errors="coerce")
    frame["sex"] = frame["sex"].astype(str).str.strip().str.lower()
    return frame.set_index("participant")


def participant_anchors(participant: str, overview: pd.DataFrame) -> dict:
    row = overview.loc[participant]
    age = float(row["age"])
    measured_hrmax = row["measured_hrmax"]
    if pd.notna(measured_hrmax):
        hrmax = float(measured_hrmax)
        hrmax_source = "PMData participant overview (measured)"
    else:
        hrmax = 208.0 - 0.7 * age
        hrmax_source = "Tanaka age-predicted fallback"

    resting_path = BASE / participant / "fitbit" / "resting_heart_rate.json"
    sleep_score_path = BASE / participant / "fitbit" / "sleep_score.csv"
    resting_values: list[float] = []
    hrrest_source = ""
    if resting_path.exists():
        records = json.loads(resting_path.read_text(encoding="utf-8"))
        resting_values = [
            float(record.get("value", {}).get("value"))
            for record in records
            if record.get("value", {}).get("value") is not None
        ]
        hrrest_source = "median Fitbit daily resting heart rate"
    if not resting_values and sleep_score_path.exists():
        sleep = pd.read_csv(sleep_score_path)
        resting_values = pd.to_numeric(sleep.get("resting_heart_rate"), errors="coerce").dropna().tolist()
        hrrest_source = "median Fitbit sleep-score resting heart rate fallback"
    resting_values = [value for value in resting_values if 30 <= value <= 120]
    hrrest = float(np.median(resting_values)) if resting_values else float("nan")
    return {
        "participant": participant,
        "age": age,
        "sex": row["sex"],
        "hrmax": hrmax,
        "hrmax_source": hrmax_source,
        "hrrest": hrrest,
        "hrrest_source": hrrest_source,
        "hrrest_days": len(resting_values),
        "measured_hrmax_available": bool(pd.notna(measured_hrmax)),
    }


def load_daily_resting_heart_rate(participant: str) -> dict[str, float]:
    """Return valid Fitbit daily resting-HR values keyed by ISO calendar date."""
    path = BASE / participant / "fitbit" / "resting_heart_rate.json"
    if not path.exists():
        return {}
    records = json.loads(path.read_text(encoding="utf-8"))
    output: dict[str, float] = {}
    for record in records:
        value = record.get("value", {}).get("value")
        date_value = str(record.get("dateTime", ""))[:10]
        if value is None or len(date_value) != 10:
            continue
        numeric = float(value)
        if 30 <= numeric <= 120:
            output[date_value] = numeric
    return output


def build_matches(participant: str) -> pd.DataFrame:
    candidates = candidate_pairs(participant)
    if candidates.empty:
        return candidates
    candidates = candidates.copy()
    candidates["rpe_candidate_count"] = candidates.groupby("rpe_index")["exercise_index"].transform("size")
    candidates["exercise_candidate_count"] = candidates.groupby("exercise_index")["rpe_index"].transform("size")
    matches = greedy_unique_match(candidates)
    matches["match_unique_both_directions"] = (
        (matches["rpe_candidate_count"] == 1) & (matches["exercise_candidate_count"] == 1)
    )
    matches["match_primary_window"] = matches["report_delay_min"].between(15.0, 180.0)
    return matches.sort_values("exercise_start_local").reset_index(drop=True)


def collect_samples(participant: str, matches: pd.DataFrame) -> list[SessionSamples]:
    sessions = [SessionSamples() for _ in range(len(matches))]
    starts = [pd.Timestamp(value).to_pydatetime() for value in matches["exercise_start_local"]]
    ends = [pd.Timestamp(value).to_pydatetime() for value in matches["exercise_end_local"]]
    path = BASE / participant / "fitbit" / "heart_rate.json"
    for record in iter_json_array(path):
        timestamp = datetime.strptime(record["dateTime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=OSLO)
        index = bisect.bisect_right(starts, timestamp) - 1
        if index < 0 or timestamp > ends[index]:
            continue
        value = record.get("value", {})
        sessions[index].timestamps.append(timestamp)
        sessions[index].bpm.append(int(value.get("bpm")))
        sessions[index].confidence.append(int(value.get("confidence", 0)))
    return sessions


def _bin_proportions(hrr: np.ndarray, weights: np.ndarray, bin_count: int) -> np.ndarray:
    bins = np.minimum((hrr * bin_count).astype(int), bin_count - 1)
    seconds = np.array([weights[bins == index].sum() for index in range(bin_count)], dtype=float)
    return seconds / seconds.sum()


def summarize_session(
    samples: SessionSamples,
    duration_min: float,
    anchors: dict,
    exercise_start_local: datetime,
    daily_resting_hr: dict[str, float],
) -> dict:
    if not samples.timestamps:
        return {
            "hr_samples_total": 0,
            "hr_samples_valid": 0,
            "valid_hr_minutes": 0.0,
            "hr_coverage": 0.0,
            "hr_qc_primary": False,
        }
    timestamps = np.array([value.timestamp() for value in samples.timestamps], dtype=float)
    bpm = np.asarray(samples.bpm, dtype=float)
    confidence = np.asarray(samples.confidence, dtype=int)
    order = np.argsort(timestamps)
    timestamps = timestamps[order]
    bpm = bpm[order]
    confidence = confidence[order]
    unique = np.r_[True, np.diff(timestamps) > 0]
    timestamps = timestamps[unique]
    bpm = bpm[unique]
    confidence = confidence[unique]

    valid_value = (bpm >= 30) & (bpm <= 220)
    valid = valid_value & (confidence >= 2)
    intervals = np.diff(timestamps, append=np.nan)
    positive = intervals[np.isfinite(intervals) & (intervals > 0) & (intervals <= GAP_CAP_SECONDS)]
    terminal = float(np.median(positive)) if len(positive) else 5.0
    intervals[-1] = min(terminal, GAP_CAP_SECONDS)
    continuous = (intervals > 0) & (intervals <= GAP_CAP_SECONDS)
    weights = np.where(valid & continuous, intervals, 0.0)
    valid_seconds = float(weights.sum())
    coverage = min(valid_seconds / max(duration_min * 60.0, 1.0), 1.0)

    hrrest = float(anchors["hrrest"])
    hrmax = float(anchors["hrmax"])
    anchor_valid = math.isfinite(hrrest) and math.isfinite(hrmax) and hrmax > hrrest + 20
    if not anchor_valid or valid_seconds <= 0:
        return {
            "hr_samples_total": int(len(bpm)),
            "hr_samples_valid": int(valid.sum()),
            "valid_hr_minutes": valid_seconds / 60.0,
            "hr_coverage": coverage,
            "hr_qc_primary": False,
        }

    valid_bpm = bpm[weights > 0]
    valid_weights = weights[weights > 0]
    valid_confidence = confidence[weights > 0]
    hrr_unclipped = (valid_bpm - hrrest) / (hrmax - hrrest)
    hrr = np.clip(hrr_unclipped, 0.0, 1.0)
    proportions = _bin_proportions(hrr, valid_weights, 10)
    proportions_5 = _bin_proportions(hrr, valid_weights, 5)
    proportions_20 = _bin_proportions(hrr, valid_weights, 20)
    linear_score = float(np.dot(proportions, np.arange(1, 11)))
    mean_hrr = float(np.average(hrr, weights=valid_weights))
    sex = str(anchors["sex"])
    if sex.startswith("female"):
        alpha, beta = 0.86, 1.67
    else:
        alpha, beta = 0.64, 1.92
    trimp_integral = float(
        np.sum((valid_weights / 60.0) * hrr * alpha * np.exp(beta * hrr))
    )
    output = {
        "hr_samples_total": int(len(bpm)),
        "hr_samples_valid": int(valid.sum()),
        "valid_hr_minutes": valid_seconds / 60.0,
        "hr_coverage": coverage,
        "median_sampling_interval_s": float(np.median(positive)) if len(positive) else float("nan"),
        "confidence3_fraction": float(np.sum(valid_weights[valid_confidence == 3]) / valid_seconds),
        "mean_hr_bpm": float(np.average(valid_bpm, weights=valid_weights)),
        "peak_hr_bpm": float(np.max(valid_bpm)),
        "mean_hrr": mean_hrr,
        "hrr_below_zero_fraction": float(np.sum(valid_weights[hrr_unclipped < 0]) / valid_seconds),
        "hrr_above_one_fraction": float(np.sum(valid_weights[hrr_unclipped > 1]) / valid_seconds),
        "linear_score": linear_score,
        "banister_trimp_integral": trimp_integral,
        "hr_qc_primary": bool(coverage >= MIN_COVERAGE and valid_seconds / 60.0 >= MIN_VALID_MINUTES),
    }
    output.update({f"p{index}": float(proportions[index - 1]) for index in range(1, 11)})
    output.update({f"p5_{index}": float(proportions_5[index - 1]) for index in range(1, 6)})
    output.update({f"p20_{index}": float(proportions_20[index - 1]) for index in range(1, 21)})

    # The continuous estimator is evaluated directly from time-weighted HRR samples.
    # Storing the prespecified grid avoids redistributing the raw wearable time series.
    for lam in LAMBDA_GRID:
        exponential = np.exp(float(lam) * hrr)
        numerator = float(np.sum(valid_weights * hrr * exponential))
        denominator = float(np.sum(valid_weights * exponential))
        output[f"continuous_tilt_l{int(round(lam * 10)):03d}"] = numerator / denominator

    session_date = exercise_start_local.date().isoformat()
    session_hrrest = daily_resting_hr.get(session_date)
    output["session_date_hrrest"] = float(session_hrrest) if session_hrrest is not None else float("nan")
    output["session_date_hrrest_available"] = bool(session_hrrest is not None)
    if session_hrrest is not None and hrmax > float(session_hrrest) + 20:
        hrr_daily_unclipped = (valid_bpm - float(session_hrrest)) / (hrmax - float(session_hrrest))
        hrr_daily = np.clip(hrr_daily_unclipped, 0.0, 1.0)
        daily_proportions = _bin_proportions(hrr_daily, valid_weights, 10)
        output["mean_hrr_session_date_rest"] = float(np.average(hrr_daily, weights=valid_weights))
        output["hrr_daily_below_zero_fraction"] = float(
            np.sum(valid_weights[hrr_daily_unclipped < 0]) / valid_seconds
        )
        output["hrr_daily_above_one_fraction"] = float(
            np.sum(valid_weights[hrr_daily_unclipped > 1]) / valid_seconds
        )
        output.update(
            {f"p10_daily_{index}": float(daily_proportions[index - 1]) for index in range(1, 11)}
        )
    else:
        output["mean_hrr_session_date_rest"] = float("nan")
        output["hrr_daily_below_zero_fraction"] = float("nan")
        output["hrr_daily_above_one_fraction"] = float("nan")
        output.update({f"p10_daily_{index}": float("nan") for index in range(1, 11)})
    return output


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    overview = load_participant_overview()
    session_rows: list[dict] = []
    anchor_rows: list[dict] = []
    participants = sorted(path.name for path in BASE.glob("p[0-9][0-9]") if path.name != "p16")
    for participant in participants:
        anchors = participant_anchors(participant, overview)
        daily_resting_hr = load_daily_resting_heart_rate(participant)
        anchor_rows.append(anchors)
        matches = build_matches(participant)
        samples = collect_samples(participant, matches)
        for session_number, (match, sample) in enumerate(zip(matches.to_dict("records"), samples), start=1):
            exercise_start_local = pd.Timestamp(match["exercise_start_local"]).to_pydatetime()
            summary = summarize_session(
                sample,
                float(match["exercise_duration_min"]),
                anchors,
                exercise_start_local,
                daily_resting_hr,
            )
            rpe = pd.to_numeric(pd.Series([match["rpe"]]), errors="coerce").iloc[0]
            row = {
                **anchors,
                **match,
                **summary,
                "session_number": session_number,
                "rpe_valid": bool(pd.notna(rpe) and 1 <= float(rpe) <= 10),
            }
            row["analysis_primary"] = bool(
                row["rpe_valid"]
                and row.get("match_unique_both_directions", False)
                and row.get("match_primary_window", False)
                and row.get("hr_qc_primary", False)
            )
            row["srpe_load"] = float(rpe) * float(row["rpe_duration_min"]) if row["rpe_valid"] else float("nan")
            row["linear_load"] = row.get("linear_score", float("nan")) * float(row["exercise_duration_min"])
            session_rows.append(row)
        print(json.dumps({"participant": participant, "matched_sessions": len(matches)}), flush=True)

    sessions = pd.DataFrame(session_rows)
    anchors_frame = pd.DataFrame(anchor_rows)
    sessions.to_csv(OUTPUT / "pmdata_session_level_qc.csv", index=False)
    anchors_frame.to_csv(OUTPUT / "pmdata_participant_anchors.csv", index=False)

    primary = sessions[sessions["analysis_primary"]].copy()
    primary.to_csv(OUTPUT / "pmdata_primary_analysis_sessions.csv", index=False)
    flow = {
        "rpe_records_total": int(sum(len(pd.read_csv(path)) for path in BASE.glob("p*/pmsys/srpe.csv"))),
        "matched_sessions_broad": int(len(sessions)),
        "valid_rpe": int(sessions["rpe_valid"].sum()),
        "unique_match_both_directions": int(sessions["match_unique_both_directions"].sum()),
        "report_delay_15_to_180_min": int(sessions["match_primary_window"].sum()),
        "hr_qc_pass": int(sessions["hr_qc_primary"].sum()),
        "primary_sessions": int(len(primary)),
        "primary_participants": int(primary["participant"].nunique()),
        "primary_sessions_by_participant": primary.groupby("participant").size().astype(int).to_dict(),
    }
    (OUTPUT / "sample_flow.json").write_text(json.dumps(flow, indent=2), encoding="utf-8")
    print(json.dumps(flow, indent=2), flush=True)


if __name__ == "__main__":
    main()
