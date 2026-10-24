"""Step 06: indicators -> percentiles -> pillar scores -> overall score -> momentum -> flags.

Writes pipeline/interim/index_counties.json, index_tracts.json and index_meta.json.
Every indicator is oriented so a HIGHER value means MORE housing-loss pressure.
Counties are compared with NC counties; Durham tracts with other Durham tracts.
"""
import json

import numpy as np
import pandas as pd

import config
from helpers import read_acs, require_file

# Labels, units and display rules for each indicator live in config.INDICATOR_INFO.
INDICATORS = config.INDICATOR_INFO


# ---------------------------------------------------------------------------
# Small math helpers
# ---------------------------------------------------------------------------
def divide(numerator, denominator):
    """Division that gives NaN (not infinity) when the denominator is 0 or missing."""
    return numerator / denominator.where(denominator > 0)


def percentile(values: pd.Series) -> pd.Series:
    """0–100 rank among units that have a value; the highest value gets 100. Missing stays missing."""
    return values.rank(pct=True, method="average") * 100


def tier_for(score):
    if score is None or pd.isna(score):
        return None
    for tier in config.TIERS:
        if tier["min"] <= score < tier["max"]:
            return tier["name"]
    return config.TIERS[-1]["name"]  # exactly 100


def clean(x, digits):
    """Round for JSON; NaN becomes null."""
    return None if x is None or pd.isna(x) else round(float(x), digits)


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------
def acs_indicators(acs: pd.DataFrame) -> pd.DataFrame:
    """Indicators that come straight from ACS (same formulas for counties and tracts)."""
    return pd.DataFrame({
        "severe_rent_burden": divide(acs["rent_burden_50plus"],
                                     acs["rent_burden_total"] - acs["rent_burden_not_computed"]) * 100,
        "poverty_rate": divide(acs["below_poverty"], acs["poverty_universe"]) * 100,
        "renter_share": divide(acs["renter_units"], acs["occupied_units"]) * 100,
    })


def county_indicators():
    acs = read_acs("county").set_index("fips")
    courts = pd.read_csv(require_file(config.INTERIM / "courts_county.csv", "output of 03_load_courts.py"),
                         dtype={"fips": str}).set_index("fips")
    courts_meta = json.loads((config.INTERIM / "courts_meta.json").read_text())
    fmr = pd.read_csv(config.INTERIM / "fmr_county.csv", dtype={"fips": str}).set_index("fips")
    svi = pd.read_csv(config.INTERIM / "svi_county.csv", dtype={"fips": str}).set_index("fips")
    bls = pd.read_csv(require_file(config.RAW / "bls_laus.csv", "output of 02_fetch_bls.py"), dtype={"fips": str})
    acs_meta = json.loads((config.RAW / "acs_meta.json").read_text())

    renters, owners = acs["renter_units"], acs["owner_units"]
    ind = acs_indicators(acs)

    # A: displacement pressure
    ind["eviction_rate"] = divide(courts["evictions_latest_fy"], renters) * 100
    ind["eviction_change"] = ind["eviction_rate"] - divide(courts["evictions_prev_fy"], renters) * 100
    ind["foreclosure_rate"] = divide(courts["foreclosures_12m"], owners) * 1000
    ind["foreclosure_change"] = divide(courts["foreclosures_3m"] - courts["foreclosures_3m_prev"], owners) * 1000

    # B: housing cost. Rent a 2-bedroom costs per year, divided by 30% (the affordability
    # rule of thumb), compared with what the median renter household earns.
    ind["housing_wage_gap"] = divide(fmr["fmr_2"] * 12 / 0.30, acs["median_renter_income"])
    zori_path = config.INTERIM / "zori_county.csv"
    if zori_path.exists():
        zori = pd.read_csv(zori_path, dtype={"fips": str}).set_index("fips")
        ind["rent_growth"] = (divide(zori["zori_latest"], zori["zori_prev"]) - 1) * 100

    # C: economic shock. County LAUS isn't seasonally adjusted, so compare with the same month last year.
    rates = bls.pivot(index="fips", columns="month", values="rate")
    latest = rates.columns.max()
    year_ago = str(pd.Period(latest, freq="M") - 12)
    ind["unemployment_rate"] = rates[latest]
    ind["unemployment_change"] = rates[latest] - rates[year_ago]

    # E: structural vulnerability (SVI percentiles are 0–1; show them as 0–100)
    ind["svi_household"] = svi["RPL_THEME2"] * 100
    ind["svi_housing_transport"] = svi["RPL_THEME4"] * 100

    month_name = lambda m: pd.Period(m, freq="M").strftime("%b %Y")
    vintage = {
        "eviction_rate": courts_meta["eviction_latest_fy"],
        "eviction_change": f"{courts_meta['eviction_prev_fy']} to {courts_meta['eviction_latest_fy']}",
        "foreclosure_rate": courts_meta["foreclosure_12m_window"],
        "foreclosure_change": f"{courts_meta['foreclosure_3m_window']} vs {courts_meta['foreclosure_3m_prev_window']}",
        "severe_rent_burden": acs_meta["acs_year"],
        "housing_wage_gap": f"FMR FY2027; ACS {acs_meta['acs_year']}",
        "unemployment_rate": month_name(latest),
        "unemployment_change": f"{month_name(year_ago)} to {month_name(latest)}",
        "poverty_rate": acs_meta["acs_year"],
        "renter_share": acs_meta["acs_year"],
        "svi_household": "2022",
        "svi_housing_transport": "2022",
    }
    source = {
        "eviction_rate": "nc_evictions", "eviction_change": "nc_evictions",
        "foreclosure_rate": "nc_foreclosures", "foreclosure_change": "nc_foreclosures",
        "severe_rent_burden": "acs", "housing_wage_gap": "hud_fmr", "rent_growth": "zori",
        "unemployment_rate": "bls_laus", "unemployment_change": "bls_laus",
        "poverty_rate": "acs", "renter_share": "acs",
        "svi_household": "svi", "svi_housing_transport": "svi",
    }
    names = acs["NAME"].str.replace(" County, North Carolina", "", regex=False)
    return ind, acs["population"], names, vintage, source


def tract_indicators():
    acs = read_acs("tract").set_index("geoid")
    evictions = pd.read_csv(config.INTERIM / "durham_evictions_tract.csv", dtype={"geoid": str}).set_index("geoid")
    svi = pd.read_csv(config.INTERIM / "svi_tract.csv", dtype={"geoid": str}).set_index("geoid")
    other_meta = json.loads((config.INTERIM / "other_meta.json").read_text())
    acs_meta = json.loads((config.RAW / "acs_meta.json").read_text())

    ind = acs_indicators(acs)
    ind["eviction_rate"] = divide(evictions["evictions"].reindex(acs.index), acs["renter_units"]) * 100
    ind["unemployment_rate"] = divide(acs["unemployed"], acs["civilian_labor_force"]) * 100
    ind["svi_household"] = svi["RPL_THEME2"] * 100
    ind["svi_housing_transport"] = svi["RPL_THEME4"] * 100

    # Tracts with no households (e.g. Duke's dorms, where everyone lives in group quarters)
    # can't have housing-loss pressure in the sense this index measures. Their few
    # remaining numbers (like student unemployment) would rank them misleadingly high,
    # so they are left unscored and show as "No data".
    no_households = acs["occupied_units"].fillna(0) == 0
    ind.loc[no_households, :] = np.nan
    print(f"Durham tracts with no households (not scored): {sorted(acs.index[no_households])}")

    year = str(other_meta["durham_eviction_year"])
    vintage = {
        "eviction_rate": f"{year} (Compass); ACS {acs_meta['acs_year']}",
        "severe_rent_burden": acs_meta["acs_year"], "poverty_rate": acs_meta["acs_year"],
        "renter_share": acs_meta["acs_year"], "unemployment_rate": acs_meta["acs_year"],
        "svi_household": "2022", "svi_housing_transport": "2022",
    }
    source = {
        "eviction_rate": "durham_compass", "severe_rent_burden": "acs", "poverty_rate": "acs",
        "renter_share": "acs", "unemployment_rate": "acs",
        "svi_household": "svi", "svi_housing_transport": "svi",
    }
    # "Census Tract 17.07; Durham County; North Carolina" -> "Tract 17.07"
    names = "Tract " + acs["NAME"].str.extract(r"Census Tract ([\d.]+)")[0]
    return ind, acs["population"], names, vintage, source


# ---------------------------------------------------------------------------
# Scoring (spec §4.4)
# ---------------------------------------------------------------------------
def pillar_scores(pct: pd.DataFrame):
    """Weighted mean of the available indicator percentiles inside each pillar.

    Returns (scores, coverage, weight_used) DataFrames with one column per pillar.
    weight_used = the indicator weights that actually had a value, per unit.
    """
    scores, coverage, used = {}, {}, {}
    for key in config.PILLARS:
        weights = pd.Series({k: v["weight"] for k, v in config.INDICATOR_WEIGHTS.items()
                             if v["pillar"] == key})
        present = [k for k in weights.index if k in pct.columns]
        w = weights[present]
        available = pct[present].notna().mul(w).sum(axis=1) if present else pd.Series(0.0, index=pct.index)
        weighted = pct[present].fillna(0).mul(w).sum(axis=1) if present else pd.Series(0.0, index=pct.index)
        # Round pillar scores here: the site recomputes the overall score from these rounded
        # values, and it must get exactly the same answer as Python (the parity check).
        scores[key] = divide(weighted, available).round(2)
        coverage[key] = available / weights.sum()
        used[key] = available
    return pd.DataFrame(scores), pd.DataFrame(coverage), pd.DataFrame(used)


def overall_score(pillars: pd.DataFrame, pillar_weights: dict) -> pd.Series:
    """Σ(pillar weight × pillar score) ÷ Σ(pillar weight for pillars that have a score)."""
    w = pd.Series(pillar_weights)
    numerator = pillars.fillna(0).mul(w).sum(axis=1)
    denominator = pillars.notna().mul(w).sum(axis=1)
    return divide(numerator, denominator)


def momentum_score(pct: pd.DataFrame) -> pd.Series:
    w = pd.Series({k: v for k, v in config.MOMENTUM_WEIGHTS.items() if k in pct.columns})
    available = pct[w.index].notna().mul(w).sum(axis=1)
    return divide(pct[w.index].fillna(0).mul(w).sum(axis=1), available)


# ---------------------------------------------------------------------------
# Driver sentences (templates, no AI)
# ---------------------------------------------------------------------------
def ordinal(n):
    n = int(n)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def format_value(key, value):
    info = INDICATORS[key]
    number = f"{value:{'+' if info.get('signed') else ''}.{info['decimals']}f}"
    if info["unit"] == "%":
        return f"{number}%"
    if info["unit"] == "percentage points":
        return f"{number} percentage points"
    if info["unit"] == "percentile":
        return f"{ordinal(value)} percentile statewide"
    if key == "housing_wage_gap":
        return f"{number}× what the typical renter can afford for a 2-bedroom"
    if key == "severe_rent_burden":
        return f"{number}% of renters"
    if key == "renter_share":
        return f"{number}% of households"
    return f"{number} {info['unit']}"


def driver_sentence(key, value, values: pd.Series, peers: str):
    # "Higher than X% of NC counties" = share of the *other* units with a lower value.
    others = values.dropna()
    share = (others < value).sum() / max(len(others) - 1, 1) * 100
    return f"{INDICATORS[key]['label']}: {format_value(key, value)} — higher than {share:.0f}% of {peers}."


# ---------------------------------------------------------------------------
# Put it together
# ---------------------------------------------------------------------------
def build(ind, population, names, vintage, source, peers, id_field, with_momentum):
    pct = ind.apply(percentile)
    scored_indicators = [k for k in config.INDICATOR_WEIGHTS if k in ind.columns]
    pillars, pillar_cov, used = pillar_scores(pct[scored_indicators])
    pillar_w = {k: v["weight"] for k, v in config.PILLARS.items()}
    score = overall_score(pillars, pillar_w).round(2)
    coverage = used.sum(axis=1) / 100
    rank = score.rank(ascending=False, method="min")
    momentum = momentum_score(pct) if with_momentum else None
    weight_of_present_pillars = pillars.notna().mul(pd.Series(pillar_w)).sum(axis=1)

    units = []
    for uid in ind.index:
        # Contribution of each indicator to the overall score. Dividing by the weight of the
        # pillars that have data (not by 100) makes the contributions add up to the score.
        contributions = {}
        for key in scored_indicators:
            p = config.INDICATOR_WEIGHTS[key]["pillar"]
            if pd.notna(pct.at[uid, key]) and used.at[uid, p] > 0:
                share_in_pillar = config.INDICATOR_WEIGHTS[key]["weight"] / used.at[uid, p]
                contributions[key] = (pillar_w[p] * share_in_pillar / weight_of_present_pillars[uid]) * pct.at[uid, key]
        top = sorted(contributions.items(), key=lambda kv: kv[1], reverse=True)[:3]

        unit = {
            id_field: uid,
            "name": names[uid],
            "population": None if pd.isna(population[uid]) else int(population[uid]),
            "indicators": {
                key: {
                    "value": clean(ind.at[uid, key], 4),
                    "pct": clean(pct.at[uid, key], 1),
                    "unit": INDICATORS[key]["unit"],
                    "source": source[key],
                    "vintage": vintage[key],
                }
                for key in ind.columns
            },
            "pillars": {
                p: None if pd.isna(pillars.at[uid, p])
                else {"score": clean(pillars.at[uid, p], 2), "coverage": clean(pillar_cov.at[uid, p], 3)}
                for p in config.PILLARS
            },
            "score": clean(score[uid], 2),
            "tier": tier_for(score[uid]),
            "rank": None if pd.isna(rank[uid]) else int(rank[uid]),
            "coverage": clean(coverage[uid], 3),
            "partial_data": bool(coverage[uid] < config.PARTIAL_DATA_COVERAGE),
            "top_drivers": [
                {"indicator": key, "contribution": clean(c, 2),
                 "sentence": driver_sentence(key, ind.at[uid, key], ind[key], peers)}
                for key, c in top
            ],
        }
        if with_momentum:
            unit["momentum"] = clean(momentum[uid], 2)
            unit["momentum_tier"] = tier_for(momentum[uid])
            unit["rising"] = bool(momentum[uid] >= config.RISING_MOMENTUM_MIN
                                  and score[uid] >= config.RISING_SCORE_MIN)
            # Small counties have noisy rates: show a badge, don't hide them.
            unit["low_reliability"] = bool(population[uid] < config.LOW_RELIABILITY_POPULATION)
        else:
            # The population rule is for counties; every tract is below 10,000 by design.
            unit["low_reliability"] = False
        units.append(unit)
    return sorted(units, key=lambda u: (u["rank"] is None, u["rank"] or 0))


def main():
    ind, pop, names, vintage, source = county_indicators()
    counties = build(ind, pop, names, vintage, source, "NC counties", "fips", with_momentum=True)

    t_ind, t_pop, t_names, t_vintage, t_source = tract_indicators()
    tracts = build(t_ind, t_pop, t_names, t_vintage, t_source, "Durham tracts", "geoid", with_momentum=False)

    missing_optional = [s["id"] for s in config.SOURCES
                        if s["optional"] and s["used_for"] not in ("Validation",)
                        and not all(p.exists() for p in s["files"])]
    meta = {"missing_optional_sources": missing_optional}

    config.INTERIM.mkdir(parents=True, exist_ok=True)
    (config.INTERIM / "index_counties.json").write_text(json.dumps(counties, indent=1, ensure_ascii=False))
    (config.INTERIM / "index_tracts.json").write_text(json.dumps(tracts, indent=1, ensure_ascii=False))
    (config.INTERIM / "index_meta.json").write_text(json.dumps(meta, indent=2))

    print(f"Scored {len(counties)} counties and {len(tracts)} Durham tracts. "
          f"Missing optional sources: {missing_optional or 'none'}.")
    print_top(counties, "counties", "name")
    print_top(tracts, "Durham tracts", "name", n=5)


def print_top(units, label, name_field, n=15):
    print(f"\nTop {n} {label} by HomeSignal score")
    print(f"{'#':>3} {'name':<14} {'score':>5} {'tier':<9} {'mom.':>5} rising  drivers")
    for u in units[:n]:
        drivers = ", ".join(d["indicator"] for d in u["top_drivers"])
        mom = u.get("momentum")
        print(f"{u['rank']:>3} {str(u[name_field]):<14} {u['score']:>5.1f} {u['tier']:<9} "
              f"{'' if mom is None else f'{mom:5.1f}':>5} {'▲' if u.get('rising') else ' ':^6}  {drivers}")
        print(f"{'':>4}↳ {u['top_drivers'][0]['sentence']}")


if __name__ == "__main__":
    main()
