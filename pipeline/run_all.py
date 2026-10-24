"""Run every pipeline step in order and stop at the first one that fails.

Usage (from the project root):  .venv/bin/python pipeline/run_all.py
Add --template-briefs to skip the Gemini API and use template briefs (marked as fallbacks).
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = [
    "00_check_raw.py",
    "01_fetch_acs.py",
    "02_fetch_bls.py",
    "03_load_courts.py",
    "04_load_other.py",
    "05_build_geo.py",
    "06_build_index.py",
    "07_validate.py",
    "08_briefs.py",
    "09_export.py",
]

skipped = []
for step in STEPS:
    script = HERE / step
    if not script.exists():
        # Steps are added phase by phase; later steps still run on what exists.
        print(f"\n--- {step}: not built yet, skipping.")
        skipped.append(step)
        continue
    print(f"\n=== {step} ===")
    args = ["--template-only"] if step == "08_briefs.py" and "--template-briefs" in sys.argv else []
    result = subprocess.run([sys.executable, str(script), *args], cwd=HERE)
    if result.returncode != 0:
        sys.exit(f"\n{step} failed (exit code {result.returncode}). Fix it and run again.")

print(f"\nFinished. Skipped (not built yet): {skipped}" if skipped else "\nAll steps finished.")
