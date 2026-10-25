"""The JSON files in site/src/data/ match the data contracts in spec §5."""
import json

import pytest

import config

DATA = config.SITE_DATA
COUNTIES = json.loads((DATA / "counties.json").read_text())
TRACTS = json.loads((DATA / "durham_tracts.json").read_text())
BOTH = [("counties", COUNTIES, "fips"), ("tracts", TRACTS, "geoid")]

UNIT_KEYS = {"name", "population", "indicators", "pillars", "score", "tier", "rank",
             "coverage", "low_reliability", "partial_data", "top_drivers"}
COUNTY_ONLY = {"momentum", "momentum_tier", "rising", "unemployment_series"}


@pytest.mark.parametrize("label,data,id_field", BOTH)
def test_meta_block(label, data, id_field):
    meta = data["meta"]
    for key in ["generated_at", "acs_year", "pillars", "indicator_weights", "tiers", "missing_optional_sources"]:
        assert key in meta, f"{label} meta is missing {key}"
    assert meta["generated_at"].endswith("Z")
    assert len(meta["pillars"]) == 4
    assert sum(p["weight"] for p in meta["pillars"].values()) == 85


@pytest.mark.parametrize("label,data,id_field", BOTH)
def test_unit_shape(label, data, id_field):
    for u in data["units"]:
        expected = UNIT_KEYS | {id_field} | (COUNTY_ONLY if label == "counties" else set())
        assert set(u) == expected, f"{label} {u[id_field]}: keys differ by {set(u) ^ expected}"
        assert isinstance(u[id_field], str)
        assert set(u["pillars"]) == set(config.PILLARS)
        for ind in u["indicators"].values():
            assert set(ind) == {"value", "pct", "unit", "source", "vintage"}
        for d in u["top_drivers"]:
            assert set(d) == {"indicator", "contribution", "sentence"}


def test_unemployment_series_is_24_months():
    for u in COUNTIES["units"]:
        series = u["unemployment_series"]
        assert len(series) == 24
        assert [p["month"] for p in series] == sorted(p["month"] for p in series)


def compute_scores(units, pillar_weights):
    """Python copy of computeScores in site/src/components/scoring.js (spec §4.5, step 4)."""
    out = {}
    for u in units:
        num = den = 0.0
        for p, w in pillar_weights.items():
            pillar = u["pillars"][p]
            if pillar is not None:
                num += w * pillar["score"]
                den += w
        out[u.get("fips") or u["geoid"]] = num / den if den > 0 else None
    return out


@pytest.mark.parametrize("label,data,id_field", BOTH)
def test_parity_with_client_side_formula(label, data, id_field):
    defaults = {k: v["weight"] for k, v in data["meta"]["pillars"].items()}
    recomputed = compute_scores(data["units"], defaults)
    for u in data["units"]:
        mine = recomputed[u[id_field]]
        if u["score"] is None:
            assert mine is None
        else:
            assert abs(mine - u["score"]) < 0.01, f"{label} {u[id_field]}: {mine} vs {u['score']}"


def test_validation_shape():
    v = json.loads((DATA / "validation.json").read_text())
    for key in ("student", "pit"):
        assert {"points", "rho", "n", "interpretation"} <= set(v[key])
        if v[key]["rho"] is not None:
            assert v[key]["interpretation"].split()[0].lower() in {"weak", "modest", "moderate", "strong"}
    assert {"median_top10_overlap", "p10", "runs"} <= set(v["stability"])
    assert v["stability"]["runs"] == 500


def test_sources_list():
    sources = json.loads((DATA / "sources.json").read_text())
    by_id = {s["id"]: s for s in sources}
    assert set(by_id) == {s["id"] for s in config.SOURCES}
    for s in config.SOURCES:
        entry = by_id[s["id"]]
        assert entry["status"] in ("used", "missing-optional")
        if not s["optional"]:
            assert entry["status"] == "used" and entry["vintage"]


def test_missing_optional_sources_are_reported_consistently():
    sources = {s["id"]: s["status"] for s in json.loads((DATA / "sources.json").read_text())}
    for sid in COUNTIES["meta"]["missing_optional_sources"]:
        assert sources[sid] == "missing-optional"


def test_total_site_data_is_small():
    total = sum(p.stat().st_size for p in DATA.iterdir() if p.is_file())
    assert total < 1.5 * 1024 * 1024, "site data should stay well under the 2.5 MB page budget"
