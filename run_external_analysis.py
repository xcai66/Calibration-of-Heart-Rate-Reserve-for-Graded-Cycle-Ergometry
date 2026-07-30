from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "external_validation" / "scripts"
STEPS = [
    "analyze_malaga_external.py",
    "analyze_malaga_secondary.py",
    "analyze_malaga_sensitivity.py",
    "analyze_weee_external.py",
]


def main() -> None:
    for script in STEPS:
        path = SCRIPTS / script
        print(f"Running {path.relative_to(ROOT)}", flush=True)
        subprocess.run([sys.executable, str(path)], cwd=SCRIPTS, check=True)
    print("External analyses completed. Run `npm run external-figure` for Figure 6.")


if __name__ == "__main__":
    main()
