#!/usr/bin/env python3
"""Apply the locked CycHRR-T function to a heart-rate CSV.

Required input column: ``hr`` (beats/min).
Optional input column: ``duration_seconds`` (positive duration represented by a row).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


TAIL_START = 0.90
TAIL_WEIGHT = 5.75
NORMALIZER = 1.0 + TAIL_WEIGHT * (1.0 - TAIL_START) ** 2


def cychrr_transfer(hrr: np.ndarray | pd.Series | float) -> np.ndarray:
    """Return CycHRR-T after clipping HRR to the validated [0, 1] domain."""

    h = np.clip(np.asarray(hrr, dtype=float), 0.0, 1.0)
    return (h + TAIL_WEIGHT * np.maximum(h - TAIL_START, 0.0) ** 2) / NORMALIZER


def summarize_session(
    transformed: np.ndarray | pd.Series,
    duration_seconds: np.ndarray | pd.Series | None = None,
) -> tuple[float, float]:
    """Return descriptive mean intensity (%) and duration-weighted exposure."""

    values = np.asarray(transformed, dtype=float)
    if duration_seconds is None:
        weights = np.ones(values.size, dtype=float)
    else:
        weights = np.asarray(duration_seconds, dtype=float)
    if values.size == 0 or values.size != weights.size:
        raise ValueError("Intensity and duration arrays must be non-empty and equal in length.")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(weights)):
        raise ValueError("Intensity and duration values must be finite.")
    if np.any(weights <= 0):
        raise ValueError("All duration weights must be positive.")
    mean_intensity = float(np.average(values, weights=weights))
    intensity_score = 100.0 * mean_intensity
    duration_minutes = float(weights.sum() / 60.0)
    dose = duration_minutes * mean_intensity
    return intensity_score, dose


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply the locked cycle-ergometry-derived HRR transfer to a CSV."
    )
    parser.add_argument("input", type=Path, help="Input CSV containing an 'hr' column.")
    parser.add_argument("output", type=Path, help="Destination CSV.")
    parser.add_argument("--rest-hr", type=float, required=True, help="Resting HR in beats/min.")
    parser.add_argument("--max-hr", type=float, required=True, help="Maximal HR in beats/min.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not np.isfinite(args.rest_hr) or not np.isfinite(args.max_hr):
        raise ValueError("HR anchors must be finite.")
    if args.max_hr <= args.rest_hr:
        raise ValueError("--max-hr must be greater than --rest-hr.")

    frame = pd.read_csv(args.input)
    if "hr" not in frame.columns:
        raise ValueError("Input CSV must contain an 'hr' column.")
    hr = pd.to_numeric(frame["hr"], errors="coerce").to_numpy(dtype=float)
    if not np.all(np.isfinite(hr)):
        raise ValueError("The 'hr' column contains missing or non-numeric values.")

    raw_hrr = np.clip((hr - args.rest_hr) / (args.max_hr - args.rest_hr), 0.0, 1.0)
    transformed = cychrr_transfer(raw_hrr)
    frame["hrr_raw"] = raw_hrr
    frame["cychrr_t"] = transformed

    duration = None
    if "duration_seconds" in frame.columns:
        duration = pd.to_numeric(frame["duration_seconds"], errors="coerce").to_numpy(dtype=float)
    score, dose = summarize_session(transformed, duration)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    print(f"Duration-weighted mean transformed intensity: {score:.3f}%")
    print(f"Exploratory duration-weighted exposure: {dose:.3f} transformed-intensity minutes")
    print(f"Rows written: {len(frame)}")


if __name__ == "__main__":
    main()
