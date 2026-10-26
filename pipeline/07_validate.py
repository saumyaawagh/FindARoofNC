"""Step 07: how well does the index line up with independent homelessness data, and how
sensitive is it to the exact weights we chose?

Writes pipeline/interim/validation.json with three parts:
  student    county score vs. students experiencing homelessness   (optional source)
  pit        CoC average score vs. Point-in-Time count per 10,000   (optional source)
  stability  how often the top 10 counties stay in the top 10 when weights shift ±10%
If an optional source is missing, its part says so instead of showing numbers.
"""
import json

import numpy as np
import pandas as pd

import config

RUNS = 500
SEED = 2026          # fixed, so the stability result is the same on every run
WEIGHT_SHIFT = 0.10  # each pillar weight is multiplied by a random factor in [0.9, 1.1]
TOP_N = 10


def load_counties():
    return json.loads((config.INTERIM / "index_counties.json").read_text())


def strength(rho):
    """The only words allowed to describe a correlation (spec §7.8)."""
    r = abs(rho)
    if r < 0.2:
        return "weak"
    if r < 0.4:
        return "modest"
    if r < 0.6:
        return "moderate"
    return "strong"


def describe(rho):
    direction = "positive" if rho >= 0 else "negative"
    return f"{strength(rho).capitalize()} {direction} relationship"


def spearman(x: pd.Series, y: pd.Series):
    both = pd.concat([x, y], axis=1).dropna()
    rho = both.iloc[:, 0].corr(both.iloc[:, 1], method="spearman")
    return float(rho), len(both)


def missing(source_id):
    return {"status": "missing-optional", "source": source_id, "points": [], "rho": None, "n": 0,
            "interpretation": "Data not available in this build"}


def student_check(counties):
    if not (config.MANUAL / "student_homeless_lea.csv").exists():
        return missing("student_homeless")
    # The ED Data Express export hasn't been seen yet; write this once its columns are known.
    raise SystemExit("student_homeless_lea.csv is present, but its validation code hasn't been written yet. "
                     "Inspect the file and finish student_check() in 07_validate.py.")


def pit_check(counties):
    if not (config.MANUAL / "pit_by_coc.xlsb").exists():
        return missing("hud_pit")
    raise SystemExit("pit_by_coc.xlsb is present, but its validation code hasn't been written yet. "
                     "Inspect the file and finish pit_check() in 07_validate.py.")


def stability_check(counties):
    """Re-score counties with randomly nudged pillar weights and count how many of the
    original top 10 stay in the top 10."""
    ids = [u["fips"] for u in counties]
    pillar_keys = list(config.PILLARS)
    # Pillar scores as a matrix (counties × pillars); NaN where a pillar has no data.
    scores = np.array([[np.nan if u["pillars"][p] is None else u["pillars"][p]["score"]
                        for p in pillar_keys] for u in counties])
    has_data = ~np.isnan(scores)
    filled = np.nan_to_num(scores)
    base_weights = np.array([config.PILLARS[p]["weight"] for p in pillar_keys], dtype=float)

    def top_ids(weights):
        # Same formula as the site: weighted mean over pillars that have data.
        overall = (filled * weights).sum(axis=1) / (has_data * weights).sum(axis=1)
        return set(np.array(ids)[np.argsort(-overall)[:TOP_N]])

    baseline = top_ids(base_weights)
    rng = np.random.default_rng(SEED)
    overlaps = []
    for _ in range(RUNS):
        factors = rng.uniform(1 - WEIGHT_SHIFT, 1 + WEIGHT_SHIFT, size=len(base_weights))
        overlaps.append(len(baseline & top_ids(base_weights * factors)))

    median, p10 = float(np.median(overlaps)), float(np.percentile(overlaps, 10))
    return {
        "runs": RUNS,
        "seed": SEED,
        "weight_shift": WEIGHT_SHIFT,
        "median_top10_overlap": median,
        "p10": p10,
        "min_top10_overlap": int(min(overlaps)),
        "sentence": (f"Across {RUNS} weight variations, a median of {median:g} of the top 10 counties "
                     f"stayed in the top 10 (10th percentile: {p10:g})."),
    }


def main():
    counties = load_counties()
    result = {
        "student": student_check(counties),
        "pit": pit_check(counties),
        "stability": stability_check(counties),
    }
    (config.INTERIM / "validation.json").write_text(json.dumps(result, indent=2))
    for key in ("student", "pit"):
        part = result[key]
        if part["rho"] is None:
            print(f"{key}: {part['interpretation']}")
        else:
            print(f"{key}: rho = {part['rho']:.2f} (n = {part['n']}), {part['interpretation']}")
    print(f"stability: {result['stability']['sentence']}")


if __name__ == "__main__":
    main()
