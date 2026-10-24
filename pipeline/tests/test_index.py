"""The scored index follows the rules in spec §4.4 and §9."""
import json
import math

import pandas as pd
import pytest

import config
import helpers

COUNTIES = json.loads((config.INTERIM / "index_counties.json").read_text())
TRACTS = json.loads((config.INTERIM / "index_tracts.json").read_text())
BOTH = [("counties", COUNTIES), ("tracts", TRACTS)]


def in_range(x):
    return x is None or 0 <= x <= 100


def test_exactly_100_counties_with_valid_fips():
    fips = [u["fips"] for u in COUNTIES]
    assert len(fips) == len(set(fips)) == 100
    assert all(isinstance(f, str) and len(f) == 5 and f.startswith("37") for f in fips)


def test_durham_tract_geoids():
    geoids = [u["geoid"] for u in TRACTS]
    assert len(geoids) == len(set(geoids)) == 68
    assert all(len(g) == 11 and g.startswith(config.DURHAM_FIPS) for g in geoids)


@pytest.mark.parametrize("label,units", BOTH)
def test_all_scores_between_0_and_100(label, units):
    for u in units:
        assert in_range(u["score"]) and in_range(u.get("momentum"))
        assert all(p is None or in_range(p["score"]) for p in u["pillars"].values())
        assert all(in_range(i["pct"]) for i in u["indicators"].values())


@pytest.mark.parametrize("label,units", BOTH)
def test_highest_eviction_rate_has_percentile_100(label, units):
    # Orientation check: higher value = worse = higher percentile.
    rated = [u for u in units if u["indicators"]["eviction_rate"]["value"] is not None]
    top = max(rated, key=lambda u: u["indicators"]["eviction_rate"]["value"])
    assert top["indicators"]["eviction_rate"]["pct"] == 100


@pytest.mark.parametrize("label,units", BOTH)
def test_score_only_missing_when_no_data(label, units):
    for u in units:
        if u["score"] is None:
            assert u["coverage"] == 0, f"{label} {u['name']} has data but no score"


@pytest.mark.parametrize("label,units", BOTH)
def test_no_placeholder_indicator_columns(label, units):
    # A column where every unit has the same value smells like a filled-in placeholder.
    for key in units[0]["indicators"]:
        values = {u["indicators"][key]["value"] for u in units} - {None}
        assert len(values) > 1, f"{label}: indicator {key} has a single repeated value {values}"


@pytest.mark.parametrize("label,units", BOTH)
def test_tier_matches_score(label, units):
    for u in units:
        if u["score"] is None:
            assert u["tier"] is None
            continue
        tier = next(t for t in config.TIERS if t["min"] <= u["score"] < t["max"] or u["score"] == 100)
        assert u["tier"] == tier["name"]


def test_rising_flag_rule():
    for u in COUNTIES:
        expected = u["momentum"] >= config.RISING_MOMENTUM_MIN and u["score"] >= config.RISING_SCORE_MIN
        assert u["rising"] == expected


def test_ranks_follow_scores():
    ordered = sorted(COUNTIES, key=lambda u: u["rank"])
    scores = [u["score"] for u in ordered]
    assert scores == sorted(scores, reverse=True)
    assert ordered[0]["rank"] == 1


@pytest.mark.parametrize("label,units", BOTH)
def test_top_drivers_are_the_biggest_contributions(label, units):
    for u in units:
        if u["score"] is None:
            continue
        contributions = [d["contribution"] for d in u["top_drivers"]]
        assert 1 <= len(contributions) <= 3
        assert contributions == sorted(contributions, reverse=True)
        # Contributions are shares of the score, so the top 3 can't add up to more than it.
        assert sum(contributions) <= u["score"] + 0.05


def test_durham_eviction_rate_matches_raw_files():
    # Recompute one number straight from the sources, independently of 06_build_index.py.
    courts = pd.read_csv(config.INTERIM / "courts_county.csv", dtype={"fips": str}).set_index("fips")
    acs = helpers.read_acs("county").set_index("fips")
    expected = courts.at["37063", "evictions_latest_fy"] / acs.at["37063", "renter_units"] * 100
    durham = next(u for u in COUNTIES if u["fips"] == "37063")
    assert math.isclose(durham["indicators"]["eviction_rate"]["value"], expected, abs_tol=1e-3)


def test_small_counties_get_low_reliability_badge():
    for u in COUNTIES:
        assert u["low_reliability"] == (u["population"] < config.LOW_RELIABILITY_POPULATION)
