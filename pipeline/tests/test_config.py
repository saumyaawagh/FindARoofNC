"""The weights and tiers in config.py match the spec (§4.4)."""
import config


def test_pillar_weights_sum_to_100():
    assert sum(p["weight"] for p in config.PILLARS.values()) == 100


def test_indicator_weights_add_up_to_their_pillar():
    for key, pillar in config.PILLARS.items():
        inside = sum(i["weight"] for i in config.INDICATOR_WEIGHTS.values() if i["pillar"] == key)
        assert inside == pillar["weight"], f"pillar {key}: indicators sum to {inside}"


def test_indicator_weights_match_spec_table():
    expected = {
        "eviction_rate": 20, "foreclosure_rate": 5, "eviction_change": 5,
        "severe_rent_burden": 12, "housing_wage_gap": 8, "rent_growth": 5,
        "unemployment_rate": 10, "unemployment_change": 10,
        "requests_211_rate": 10, "requests_211_change": 5,
        "poverty_rate": 4, "renter_share": 2, "svi_household": 2, "svi_housing_transport": 2,
    }
    assert {k: v["weight"] for k, v in config.INDICATOR_WEIGHTS.items()} == expected


def test_momentum_weights_sum_to_100():
    assert sum(config.MOMENTUM_WEIGHTS.values()) == 100


def test_tiers_cover_0_to_100_without_gaps():
    tiers = config.TIERS
    assert tiers[0]["min"] == 0 and tiers[-1]["max"] == 100
    for lower, upper in zip(tiers, tiers[1:]):
        assert lower["max"] == upper["min"]
    assert [t["name"] for t in tiers] == ["Low", "Guarded", "Elevated", "High", "Priority"]


def test_source_ids_are_unique():
    ids = [s["id"] for s in config.SOURCES]
    assert len(ids) == len(set(ids))
