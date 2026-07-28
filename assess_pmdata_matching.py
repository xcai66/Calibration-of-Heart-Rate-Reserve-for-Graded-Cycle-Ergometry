from __future__ import annotations

import ast
import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
BASE = Path(os.environ.get("PMDATA_ROOT", PROJECT_ROOT / "source" / "pmdata")).expanduser().resolve()
ANALYSIS = PROJECT_ROOT / "analysis"
OSLO = ZoneInfo("Europe/Oslo")


def parse_rpe_activities(value: str) -> set[str]:
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        parsed = [value]
    return {str(item).strip().lower() for item in parsed}


def compatible(rpe_activities: set[str], exercise_name: str) -> bool:
    name = exercise_name.strip().lower()
    aliases = {
        "run": {"running", "endurance", "individual"},
        "treadmill": {"running", "endurance", "individual"},
        "bike": {"cycling", "endurance", "individual"},
        "outdoor bike": {"cycling", "endurance", "individual"},
        "weights": {"strength", "individual"},
        "workout": {"strength", "endurance", "individual", "team", "soccer"},
        "sport": {"team", "soccer", "individual", "endurance"},
        "football": {"team", "soccer"},
        "walk": {"walking", "individual", "endurance"},
        "hike": {"walking", "hiking", "endurance", "individual"},
        "cross-country skiing": {"skiing", "endurance", "individual"},
        "elliptical": {"endurance", "individual"},
    }
    accepted = aliases.get(name, {name})
    return bool(rpe_activities & accepted)


def load_exercises(participant: str) -> pd.DataFrame:
    path = BASE / participant / "fitbit" / "exercise.json"
    records = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for idx, record in enumerate(records):
        if record.get("logType") != "tracker":
            continue
        start = datetime.strptime(record["startTime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=OSLO)
        duration_min = float(record.get("duration", 0)) / 60000.0
        rows.append(
            {
                "exercise_index": idx,
                "exercise_name": record.get("activityName", ""),
                "exercise_start_local": start,
                "exercise_end_local": start + timedelta(minutes=duration_min),
                "exercise_duration_min": duration_min,
                "average_hr": record.get("averageHeartRate"),
            }
        )
    return pd.DataFrame(rows)


def load_rpe(participant: str) -> pd.DataFrame:
    path = BASE / participant / "pmsys" / "srpe.csv"
    frame = pd.read_csv(path)
    frame["rpe_index"] = np.arange(len(frame))
    frame["report_utc"] = pd.to_datetime(frame["end_date_time"], utc=True)
    frame["report_local"] = frame["report_utc"].dt.tz_convert(OSLO)
    frame["activities"] = frame["activity_names"].astype(str).map(parse_rpe_activities)
    return frame


def candidate_pairs(participant: str) -> pd.DataFrame:
    rpe = load_rpe(participant)
    exercises = load_exercises(participant)
    rows = []
    for _, report in rpe.iterrows():
        for _, exercise in exercises.iterrows():
            gap_min = (report["report_local"] - exercise["exercise_end_local"]).total_seconds() / 60.0
            duration_diff = abs(float(report["duration_min"]) - exercise["exercise_duration_min"])
            duration_limit = max(10.0, 0.35 * float(report["duration_min"]))
            is_compatible = compatible(report["activities"], exercise["exercise_name"])
            if -15.0 <= gap_min <= 12 * 60 and duration_diff <= duration_limit and is_compatible:
                cost = abs(gap_min) / 60.0 + duration_diff / max(float(report["duration_min"]), 10.0)
                rows.append(
                    {
                        "participant": participant,
                        "rpe_index": int(report["rpe_index"]),
                        "exercise_index": int(exercise["exercise_index"]),
                        "rpe": float(report["perceived_exertion"]),
                        "rpe_duration_min": float(report["duration_min"]),
                        "rpe_activity_names": report["activity_names"],
                        "report_local": report["report_local"],
                        "exercise_name": exercise["exercise_name"],
                        "exercise_start_local": exercise["exercise_start_local"],
                        "exercise_end_local": exercise["exercise_end_local"],
                        "exercise_duration_min": exercise["exercise_duration_min"],
                        "average_hr": exercise["average_hr"],
                        "report_delay_min": gap_min,
                        "duration_difference_min": duration_diff,
                        "cost": cost,
                    }
                )
    return pd.DataFrame(rows)


def greedy_unique_match(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return candidates.copy()
    selected = []
    used_rpe: set[int] = set()
    used_exercise: set[int] = set()
    for _, row in candidates.sort_values(["cost", "report_delay_min"]).iterrows():
        rpe_index = int(row["rpe_index"])
        exercise_index = int(row["exercise_index"])
        if rpe_index in used_rpe or exercise_index in used_exercise:
            continue
        selected.append(row)
        used_rpe.add(rpe_index)
        used_exercise.add(exercise_index)
    return pd.DataFrame(selected)


def main() -> None:
    if not (BASE / "participant-overview.xlsx").exists():
        raise FileNotFoundError(
            "PMData was not found. Set PMDATA_ROOT to the directory containing "
            "participant-overview.xlsx and participant folders p01-p16."
        )
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    participants = sorted(path.name for path in BASE.glob("p[0-9][0-9]") if path.is_dir())
    rpe_activity_counts: Counter[str] = Counter()
    tracker_activity_counts: Counter[str] = Counter()
    log_type_counts: Counter[str] = Counter()
    summaries = []
    all_matches = []
    for participant in participants:
        rpe = load_rpe(participant)
        exercises_raw = json.loads((BASE / participant / "fitbit" / "exercise.json").read_text())
        for value in rpe["activity_names"].astype(str):
            rpe_activity_counts[value] += 1
        for record in exercises_raw:
            log_type_counts[record.get("logType", "")] += 1
            if record.get("logType") == "tracker":
                tracker_activity_counts[record.get("activityName", "")] += 1
        candidates = candidate_pairs(participant)
        matches = greedy_unique_match(candidates)
        if not matches.empty:
            all_matches.append(matches)
        candidate_counts = candidates.groupby("rpe_index").size() if not candidates.empty else pd.Series(dtype=int)
        summaries.append(
            {
                "participant": participant,
                "rpe_records": len(rpe),
                "tracker_exercises": sum(record.get("logType") == "tracker" for record in exercises_raw),
                "matched_records": len(matches),
                "rpe_with_multiple_candidates": int((candidate_counts > 1).sum()),
                "median_report_delay_min": float(matches["report_delay_min"].median()) if not matches.empty else None,
                "median_duration_difference_min": float(matches["duration_difference_min"].median()) if not matches.empty else None,
            }
        )
    summary = pd.DataFrame(summaries)
    matches = pd.concat(all_matches, ignore_index=True) if all_matches else pd.DataFrame()
    summary.to_csv(ANALYSIS / "matching_feasibility_by_participant.csv", index=False)
    matches.to_csv(ANALYSIS / "matched_sessions_preview.csv", index=False)
    report = {
        "summary": {
            "participants": len(participants),
            "rpe_records": int(summary["rpe_records"].sum()),
            "tracker_exercises": int(summary["tracker_exercises"].sum()),
            "matched_records": int(summary["matched_records"].sum()),
            "participants_with_matches": int((summary["matched_records"] > 0).sum()),
            "rpe_with_multiple_candidates": int(summary["rpe_with_multiple_candidates"].sum()),
        },
        "rpe_activity_counts": dict(rpe_activity_counts.most_common()),
        "tracker_activity_counts": dict(tracker_activity_counts.most_common()),
        "log_type_counts": dict(log_type_counts.most_common()),
    }
    (ANALYSIS / "matching_feasibility_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
