"""The downloaded data has the shape and ID formats the rest of the pipeline relies on."""
import warnings

import pandas as pd
import pytest

import config
import helpers

warnings.filterwarnings("ignore", module="openpyxl")

# Court files include whole-state summary rows alongside the 100 counties.
STATE_ROWS = {"Statewide", "North Carolina", "STATEWIDE", "NORTH CAROLINA"}


def court_county_names(path, sheet, header):
    df = pd.read_excel(path, sheet_name=sheet, header=header, usecols=["County"], dtype=str)
    return sorted(set(df["County"].dropna()) - STATE_ROWS)


def test_acs_has_100_counties_with_5_char_fips():
    acs = helpers.read_acs("county")
    assert acs["fips"].nunique() == 100
    assert acs["fips"].str.len().eq(5).all()
    assert acs["fips"].str.startswith("37").all()


def test_acs_durham_tracts_are_11_char_geoids():
    tracts = helpers.read_acs("tract")
    assert tracts["geoid"].str.len().eq(11).all()
    assert tracts["geoid"].str.startswith(config.DURHAM_FIPS).all()


def test_acs_sentinels_become_missing():
    # No ACS value at or below the sentinel threshold may survive cleaning.
    for geo in ["county", "tract"]:
        acs = helpers.read_acs(geo)
        values = acs[list(config.ACS_VARIABLES.values())]
        assert not (values <= config.ACS_SENTINEL_THRESHOLD).any().any()


def test_bls_covers_all_counties_and_25_months():
    bls = pd.read_csv(config.RAW / "bls_laus.csv", dtype={"fips": str})
    assert bls["fips"].nunique() == 100
    assert bls["month"].nunique() == config.BLS_MONTHS


@pytest.mark.parametrize("name", ["civil_issues_fy24-25.xlsx", "civil_issues_fy25-26.xlsx"])
def test_civil_county_names_all_match_once(name):
    names = court_county_names(config.MANUAL / name, config.CIVIL_SHEET, header=0)
    mapping = helpers.county_name_to_fips(names)  # raises if any name fails to match exactly once
    assert len(mapping) == 100


@pytest.mark.parametrize("name", ["foreclosures_2024.xlsx", "foreclosures_2025.xlsx"])
def test_foreclosure_county_names_all_match_once(name):
    names = court_county_names(config.MANUAL / name, config.FORECLOSURE_SHEET, header=1)
    assert len(helpers.county_name_to_fips(names)) == 100


def test_county_name_matcher_rejects_unknown_names():
    names = court_county_names(config.MANUAL / "foreclosures_2025.xlsx", config.FORECLOSURE_SHEET, header=1)
    with pytest.raises(ValueError, match="Unmatched names"):
        helpers.county_name_to_fips(names + ["Narnia"])


def test_county_name_matcher_handles_mcdowell_casing():
    names = court_county_names(config.MANUAL / "foreclosures_2025.xlsx", config.FORECLOSURE_SHEET, header=1)
    mapping = helpers.county_name_to_fips(names)
    mcdowell = [n for n in names if n.lower() == "mcdowell"]
    assert mcdowell and mapping[mcdowell[0]] == "37111"


@pytest.mark.parametrize("name,length", [("svi_2022_nc_county.csv", 5), ("svi_2022_nc_tract.csv", 11)])
def test_svi_ids_are_strings_of_right_length(name, length):
    svi = pd.read_csv(config.MANUAL / name, dtype={"FIPS": str})
    assert svi["FIPS"].str.len().eq(length).all()
    assert svi["FIPS"].str.startswith("37").all()
