"""The brief safeguards work: the number check, the fixed action playbook, the template fallback."""
import importlib.util
import json

import pytest

import config

# The step file starts with a digit, so load it by path.
spec = importlib.util.spec_from_file_location("briefs", config.PIPELINE / "08_briefs.py")
briefs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(briefs)

COUNTIES = json.loads((config.INTERIM / "index_counties.json").read_text())
TRACTS = [t for t in json.loads((config.INTERIM / "index_tracts.json").read_text()) if t["score"] is not None]
UNITS = [(u, "county", len(COUNTIES)) for u in COUNTIES] + [(t, "tract", len(TRACTS)) for t in TRACTS]


def county(name):
    return next(u for u in COUNTIES if u["name"] == name)


def test_numbers_in_reads_signs_percents_and_commas():
    assert briefs.numbers_in("rose by +0.4 points to 4.8% (1,234 filings) in FY 2025-26") == [0.4, 4.8, 1234, 2025, 26]
    assert briefs.numbers_in("fell −0.5") == [-0.5]


def test_number_check_accepts_rounded_and_unsigned_facts():
    unit = county("Washington")
    facts = briefs.build_facts(unit, "county", 100)
    actions = briefs.choose_actions(unit)
    brief = briefs.template_brief(facts, actions, "county")
    brief["situation"] = f"Score {facts['score']} of 100, rank {facts['rank']}."
    assert briefs.check_brief(brief, facts, actions, "county") == []


def test_number_check_rejects_invented_numbers():
    unit = county("Washington")
    facts = briefs.build_facts(unit, "county", 100)
    actions = briefs.choose_actions(unit)
    brief = briefs.template_brief(facts, actions, "county")
    brief["situation"] = "About 4,000 families face eviction this winter."
    problems = briefs.check_brief(brief, facts, actions, "county")
    assert any("4000" in p for p in problems)


def test_number_check_rejects_wrong_actions():
    unit = county("Washington")
    facts = briefs.build_facts(unit, "county", 100)
    actions = briefs.choose_actions(unit)
    brief = briefs.template_brief(facts, actions, "county")
    brief["actions"] = brief["actions"][::-1]
    assert any("action keys" in p for p in briefs.check_brief(brief, facts, actions, "county"))


@pytest.mark.parametrize("unit,kind,total", UNITS, ids=lambda x: x.get("name") if isinstance(x, dict) else None)
def test_template_fallback_always_passes_the_check(unit, kind, total):
    facts = briefs.build_facts(unit, kind, total)
    actions = briefs.choose_actions(unit)
    assert briefs.check_brief(briefs.template_brief(facts, actions, kind), facts, actions, kind) == []


def test_actions_come_from_the_top_pillar():
    for unit, kind, total in UNITS:
        actions = [a["key"] for a in briefs.choose_actions(unit)]
        scored = {k: p["score"] for k, p in unit["pillars"].items() if p is not None}
        top = max(scored, key=lambda k: (scored[k], -list(config.PILLARS).index(k)))
        assert set(actions) <= set(briefs.PLAYBOOK[top])
        assert 2 <= len(actions) <= 3
        if "foreclosure_counseling" in actions:
            assert unit["indicators"]["foreclosure_rate"]["pct"] >= 70


def test_exported_briefs_pass_the_check_or_are_marked_fallback():
    path = config.SITE_DATA / "briefs.json"
    if not path.exists():
        pytest.skip("briefs.json not generated yet")
    data = json.loads(path.read_text())
    expected_ids = {u.get("fips") or u["geoid"] for u, _, _ in UNITS}
    assert set(data) == expected_ids
    for unit, kind, total in UNITS:
        entry = data[unit.get("fips") or unit["geoid"]]
        if entry["fallback"]:
            assert entry["model"] == "template"
            continue
        facts = briefs.build_facts(unit, kind, total)
        actions = briefs.choose_actions(unit)
        assert briefs.check_brief(entry, facts, actions, kind) == [], unit["name"]
