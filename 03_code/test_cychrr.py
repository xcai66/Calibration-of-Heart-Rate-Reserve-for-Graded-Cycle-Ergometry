#!/usr/bin/env python3
"""Regression tests for the public CycHRR-T implementation."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import numpy as np


MODULE_PATH = Path(__file__).with_name("07_apply_cychrr.py")
SPEC = importlib.util.spec_from_file_location("cychrr_apply", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CycHRRTransferTests(unittest.TestCase):
    def test_endpoints_and_clipping(self) -> None:
        values = MODULE.cychrr_transfer(np.array([-1.0, 0.0, 1.0, 2.0]))
        np.testing.assert_allclose(values, np.array([0.0, 0.0, 1.0, 1.0]), atol=1e-12)

    def test_monotonic_and_bounded(self) -> None:
        h = np.linspace(0.0, 1.0, 10001)
        g = MODULE.cychrr_transfer(h)
        self.assertTrue(np.all(np.diff(g) >= -1e-12))
        self.assertGreaterEqual(float(g.min()), 0.0)
        self.assertLessEqual(float(g.max()), 1.0)

    def test_relation_to_identity(self) -> None:
        h = np.linspace(0.0, 1.0, 10001)
        g = MODULE.cychrr_transfer(h)
        self.assertTrue(np.all(g <= h + 1e-12))
        self.assertAlmostEqual(float(g[-1]), 1.0, places=12)

    def test_session_aggregation(self) -> None:
        g = np.array([0.2, 0.4, 0.8])
        seconds = np.array([60.0, 120.0, 60.0])
        score, dose = MODULE.summarize_session(g, seconds)
        self.assertAlmostEqual(score, 45.0, places=12)
        self.assertAlmostEqual(dose, 1.8, places=12)

    def test_invalid_duration_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.summarize_session(np.array([0.2, 0.4]), np.array([60.0, 0.0]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
