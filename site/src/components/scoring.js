// The ONLY math the website does (spec §4.5): re-weight the pillar scores Python already
// computed. Everything else (percentiles, pillar scores, momentum) comes precomputed.
import {tierName} from "./palette.js";

const RISING_MOMENTUM_MIN = 75;
const RISING_SCORE_MIN = 40;

// units: the "units" array from counties.json or durham_tracts.json
// pillarWeights: {A: 30, B: 25, ...}
// Returns a Map: id -> {score, tier, rank, rising}
export function computeScores(units, pillarWeights) {
  const results = new Map();
  for (const unit of units) {
    // Weighted mean over the pillars that have data (spec §4.4 step 4).
    let numerator = 0;
    let denominator = 0;
    for (const [key, weight] of Object.entries(pillarWeights)) {
      const pillar = unit.pillars[key];
      if (pillar == null) continue;
      numerator += weight * pillar.score;
      denominator += weight;
    }
    const score = denominator > 0 ? numerator / denominator : null;
    const rising = unit.momentum != null && score != null
      && unit.momentum >= RISING_MOMENTUM_MIN && score >= RISING_SCORE_MIN;
    results.set(unitId(unit), {score, tier: tierName(score), rank: null, rising});
  }

  // Rank 1 = highest score; ties share the better rank (like pandas method="min").
  const scored = [...results.values()].filter((r) => r.score != null).sort((a, b) => b.score - a.score);
  scored.forEach((r, i) => {
    r.rank = i > 0 && r.score === scored[i - 1].score ? scored[i - 1].rank : i + 1;
  });
  return results;
}

export function unitId(unit) {
  return unit.fips ?? unit.geoid;
}

export function defaultWeights(meta) {
  return Object.fromEntries(Object.entries(meta.pillars).map(([k, p]) => [k, p.weight]));
}

// Development check: with default weights the browser must reproduce Python's scores.
export function checkParity(units, meta) {
  const mine = computeScores(units, defaultWeights(meta));
  const bad = units.filter((u) => {
    const s = mine.get(unitId(u)).score;
    return (s == null) !== (u.score == null) || (s != null && Math.abs(s - u.score) >= 0.01);
  });
  if (bad.length) {
    console.error(`Score parity check failed for ${bad.length} units, e.g.`, unitId(bad[0]),
      mine.get(unitId(bad[0])).score, "vs Python", bad[0].score);
  }
  return bad.length === 0;
}
