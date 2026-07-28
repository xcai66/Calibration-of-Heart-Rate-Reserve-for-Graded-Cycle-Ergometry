from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STEPS = [
    "assess_pmdata_matching.py",
    "build_pmdata_session_dataset.py",
    "develop_improved_formula.py",
    "analyze_improved_formula_sensitivity.py",
    "reviewer_revision_analysis.py",
    "reviewer_round2_analysis.py",
]


def main() -> None:
    pmdata_root = Path(os.environ.get("PMDATA_ROOT", ROOT / "source" / "pmdata"))
    if not pmdata_root.exists():
        raise SystemExit(
            "PMData was not found. Set PMDATA_ROOT to the licensed local PMData directory."
        )
    environment = os.environ.copy()
    environment["PMDATA_ROOT"] = str(pmdata_root.expanduser().resolve())
    for script in STEPS:
        print(f"Running {script}", flush=True)
        subprocess.run(
            [sys.executable, str(ROOT / script)],
            cwd=ROOT,
            env=environment,
            check=True,
        )
    print("Core analysis completed.")


if __name__ == "__main__":
    main()
