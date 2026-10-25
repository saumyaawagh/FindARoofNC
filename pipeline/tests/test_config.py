"""The weights and tiers in config.py match the spec (§4.4), minus the removed Help-seeking pillar."""
import config


def test_four_pillars_with_spec_weights():
    # Help-seeking (15) was removed; the others keep their spec weights and add up to 85.
    assert {p["label"]: p["weight"] for p in config.PILLARS.values()} == {
        "Displacement pressure": 30, "Housing cost pressure": 25,
        "Economic shock": 20, "Structural vulnerability": 10,
    }


def test_indicator_weights_add_up_to_their_pillar():
    for key, pillar in config.PILLARS.items():
        inside = sum(i["weight"] for i in config.INDICATOR_WEIGHTS.values() if i["pillar"] == key)
        assert inside == pillar["weight"], f"pillar {key}: indicators sum to {inside}"


def test_indicator_weights_match_spec_table():
    expected = {
        "eviction_rate": 20, "foreclosure_rate": 5, "eviction_change": 5,
        "severe_rent_burden": 12, "housing_wage_gap": 8, "rent_growth": 5,
        "unemployment_rate": 10, "unemployment_change": 10,
        "poverty_rate": 4, "renter_share": 2, "svi_household": 2, "svi_housing_transport": 2,
    }
    assert {k: v["weight"] for k, v in config.INDICATOR_WEIGHTS.items()} == expected


def test_momentum_weights_match_spec_without_211():
    assert config.MOMENTUM_WEIGHTS == {"unemployment_change": 35, "eviction_change": 25, "foreclosure_change": 20}


def test_no_help_seeking_left():
    assert all("211" not in key for key in config.INDICATOR_WEIGHTS)
    assert all(s["id"] != "nc211" for s in config.SOURCES)


def test_tiers_cover_0_to_100_without_gaps():
    tiers = config.TIERS
    assert tiers[0]["min"] == 0 and tiers[-1]["max"] == 100
    for lower, upper in zip(tiers, tiers[1:]):
        assert lower["max"] == upper["min"]
    assert [t["name"] for t in tiers] == ["Low", "Guarded", "Elevated", "High", "Priority"]


def test_source_ids_are_unique():
    ids = [s["id"] for s in config.SOURCES]
    assert len(ids) == len(set(ids))
