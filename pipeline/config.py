"""Settings shared by every pipeline step: paths, the source manifest, weights and tiers.

Change numbers here, not inside the step scripts, so there is one place to look.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
PIPELINE = ROOT / "pipeline"
RAW = PIPELINE / "raw"            # scripted downloads (gitignored)
MANUAL = PIPELINE / "manual"      # files a human downloads by hand
INTERIM = PIPELINE / "interim"    # cleaned tables passed between steps (gitignored)
SITE_DATA = ROOT / "site" / "src" / "data"

STATE_FIPS = "37"                 # North Carolina
DURHAM_FIPS = "37063"
N_COUNTIES = 100

# ---------------------------------------------------------------------------
# Census ACS 5-year
# ---------------------------------------------------------------------------
# Newest first. The fetcher uses the first year the API actually serves and prints which one.
ACS_YEARS_TO_TRY = [2025, 2024, 2023]

ACS_VARIABLES = {
    "B01003_001E": "population",
    "B25003_001E": "occupied_units",
    "B25003_002E": "owner_units",
    "B25003_003E": "renter_units",
    "B25070_001E": "rent_burden_total",
    "B25070_010E": "rent_burden_50plus",
    "B25070_011E": "rent_burden_not_computed",
    "B25119_003E": "median_renter_income",
    "B17001_001E": "poverty_universe",
    "B17001_002E": "below_poverty",
    "B23025_003E": "civilian_labor_force",
    "B23025_005E": "unemployed",
    "B09001_001E": "population_under_18",
    "B25064_001E": "median_gross_rent",
}

# ACS marks missing estimates with huge negative numbers (e.g. -666666666).
ACS_SENTINEL_THRESHOLD = -100_000_000
# SVI marks missing values with -999.
SVI_MISSING = -999

# ---------------------------------------------------------------------------
# BLS Local Area Unemployment Statistics
# ---------------------------------------------------------------------------
BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_MONTHS = 25                   # 24-month sparkline + same month a year earlier
BLS_SERIES_PER_REQUEST = 50       # API limit with a registration key


def bls_series_id(county_fips: str) -> str:
    """Unemployment rate series for one county, e.g. LAUCN370630000000003 for Durham."""
    return f"LAUCN{county_fips}0000000003"


# ---------------------------------------------------------------------------
# Court data
# ---------------------------------------------------------------------------
# Summary ejectment = the court action a landlord files to evict a tenant.
# Confirmed by the builder in Phase 1 (see pipeline/manual/README.md).
EVICTION_ISSUE_CODES = ["SUME"]
CIVIL_SHEET = "VCAP_Issues"
FORECLOSURE_SHEET = "FORE"

# ---------------------------------------------------------------------------
# Source manifest
# ---------------------------------------------------------------------------
# kind:
#   "manual"   – a human downloads it; 00_check_raw.py fails if a required one is missing
#   "scripted" – a pipeline step downloads it (fetched_by); 00_check_raw.py only reports it
# files: what must exist; columns: what must be in each file's header
SOURCES = [
    {
        "id": "acs",
        "name": "American Community Survey 5-year estimates",
        "publisher": "U.S. Census Bureau",
        "url": "https://www.census.gov/programs-surveys/acs",
        "geography": "county + Durham tracts",
        "kind": "scripted",
        "fetched_by": "01_fetch_acs.py",
        "optional": False,
        "files": [RAW / "acs_county.csv", RAW / "acs_tract.csv", RAW / "acs_meta.json"],
        "columns": {},
        "used_for": "Indicators and denominators",
    },
    {
        "id": "bls_laus",
        "name": "Local Area Unemployment Statistics",
        "publisher": "U.S. Bureau of Labor Statistics",
        "url": "https://www.bls.gov/lau/",
        "geography": "county",
        "kind": "scripted",
        "fetched_by": "02_fetch_bls.py",
        "optional": False,
        "files": [RAW / "bls_laus.csv"],
        "columns": {},
        "used_for": "Unemployment level, change and sparkline",
    },
    {
        "id": "hud_fmr",
        "name": "Fair Market Rents (FY2027)",
        "publisher": "U.S. Dept. of Housing and Urban Development",
        "url": "https://www.huduser.gov/portal/datasets/fmr.html",
        "geography": "county",
        "kind": "manual",
        "optional": False,
        "files": [MANUAL / "fmr_2027.xlsx"],
        "sheet": "FY27_FMRs",
        "columns": {"fmr_2027.xlsx": ["stusps", "fips", "countyname", "fmr_2"]},
        "used_for": "Housing wage gap",
    },
    {
        "id": "nc_evictions",
        "name": "Civil Issue Filings/Order Results",
        "publisher": "North Carolina Judicial Branch",
        "url": "https://www.nccourts.gov/documents/publications/civil-issue-filingsorder-results",
        "geography": "county",
        "kind": "manual",
        "optional": False,
        "files": [MANUAL / "civil_issues_fy24-25.xlsx", MANUAL / "civil_issues_fy25-26.xlsx"],
        "sheet": CIVIL_SHEET,
        "columns": {
            "civil_issues_fy24-25.xlsx": ["From_", "To_", "County", "Case_Type", "Issue_Code", "Issue_Text", "Total_Cases_Filed"],
            "civil_issues_fy25-26.xlsx": ["From_", "To_", "County", "Case_Type", "Issue_Code", "Issue_Text", "Total_Cases_Filed"],
        },
        "used_for": "Eviction rate and year-over-year change",
    },
    {
        "id": "nc_foreclosures",
        "name": "Foreclosure Filings",
        "publisher": "North Carolina Judicial Branch",
        "url": "https://www.nccourts.gov/documents/publications/foreclosure-filings",
        "geography": "county",
        "kind": "manual",
        "optional": False,
        "files": [MANUAL / "foreclosures_2024.xlsx", MANUAL / "foreclosures_2025.xlsx"],
        "sheet": FORECLOSURE_SHEET,
        "header_row": 1,  # row 0 is a title line
        "columns": {
            "foreclosures_2024.xlsx": ["County", "Year", "January", "December"],
            "foreclosures_2025.xlsx": ["County", "Year", "January", "December"],
        },
        "used_for": "Foreclosure rate and 3-month change",
    },
    {
        "id": "svi",
        "name": "Social Vulnerability Index 2022 (North Carolina, state-based)",
        "publisher": "CDC/ATSDR",
        "url": "https://www.atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html",
        "geography": "county + tract",
        "kind": "manual",
        "optional": False,
        "files": [MANUAL / "svi_2022_nc_county.csv", MANUAL / "svi_2022_nc_tract.csv"],
        "columns": {
            "svi_2022_nc_county.csv": ["FIPS", "RPL_THEME2", "RPL_THEME4"],
            "svi_2022_nc_tract.csv": ["FIPS", "RPL_THEME2", "RPL_THEME4"],
        },
        "used_for": "Structural vulnerability pillar",
    },
    {
        "id": "zori",
        "name": "Zillow Observed Rent Index (county, monthly)",
        "publisher": "Zillow Research",
        "url": "https://www.zillow.com/research/data/",
        "geography": "county (metro only)",
        "kind": "manual",
        "optional": True,
        "files": [MANUAL / "zori_county.csv"],
        "columns": {"zori_county.csv": ["RegionName", "StateName", "StateCodeFIPS", "MunicipalCodeFIPS"]},
        "used_for": "12-month rent growth",
    },
    {
        "id": "durham_compass",
        "name": "Durham Neighborhood Compass (summary ejectment)",
        "publisher": "DataWorks NC",
        "url": "https://github.com/DataWorks-NC/durham-quality-of-life-data",
        "geography": "Durham block groups / tracts",
        "kind": "manual",  # a one-time `git clone`, listed in the manual checklist
        "optional": False,
        "files": [RAW / "durham-quality-of-life-data" / "config" / "data.js",
                  RAW / "durham-quality-of-life-data" / "metric" / "blockgroup" / "sumeject_numerator.csv",
                  RAW / "durham-quality-of-life-data" / "metric" / "tract" / "sumeject_numerator.csv",
                  # Neighborhood boundaries, used to label tracts ("Tract 3.01 · Walltown area")
                  RAW / "durham-quality-of-life-data" / "selectgroups.geojson.json"],
        # Raw counts (the numerator), not the per-square-mile rate the Compass website maps.
        "columns": {"sumeject_numerator.csv": ["fips", "year", "value"]},
        "used_for": "Durham eviction indicator",
    },
    {
        # The Compass uses 2010 geography (only 52 of 60 tracts match 2020). Decision in Phase 1:
        # move its 2010 block-group eviction counts onto 2020 tracts, weighted by shared land area.
        "id": "blockgroup_crosswalk",
        "name": "2020 to 2010 block group relationship file",
        "publisher": "U.S. Census Bureau",
        "url": "https://www2.census.gov/geo/docs/maps-data/data/rel2020/blkgrp/tab20_blkgrp20_blkgrp10_natl.txt",
        "geography": "block group 2010 → 2020",
        "kind": "scripted",
        "fetched_by": "04_load_other.py",
        "optional": False,
        "files": [RAW / "tab20_blkgrp20_blkgrp10_natl.txt"],
        "columns": {},
        "used_for": "Moving Durham Compass evictions onto 2020 tracts",
    },
    {
        "id": "student_homeless",
        "name": "Homeless students enrolled (EDFacts file 118)",
        "publisher": "U.S. Dept. of Education, ED Data Express",
        "url": "https://eddataexpress.ed.gov/",
        "geography": "school district",
        "kind": "manual",
        "optional": True,
        "files": [MANUAL / "student_homeless_lea.csv"],
        "columns": {},  # set once a real export has been inspected
        "used_for": "Validation",
    },
    {
        "id": "lea_crosswalk",
        "name": "School district → county crosswalk",
        "publisher": "Hand-built for this project",
        "url": "",
        "geography": "school district → county",
        "kind": "manual",
        "optional": True,
        "required_if": "student_homeless",
        "files": [MANUAL / "lea_county_crosswalk.csv"],
        "columns": {"lea_county_crosswalk.csv": ["lea_name", "county_fips"]},
        "used_for": "Validation",
    },
    {
        "id": "hud_pit",
        "name": "Point-in-Time counts by CoC",
        "publisher": "U.S. Dept. of Housing and Urban Development",
        "url": "https://www.huduser.gov/portal/datasets/ahar.html",
        "geography": "Continuum of Care",
        "kind": "manual",
        "optional": True,
        "files": [MANUAL / "pit_by_coc.xlsb"],
        "columns": {},
        "used_for": "Validation",
    },
    {
        "id": "coc_crosswalk",
        "name": "County → CoC crosswalk",
        "publisher": "Hand-built for this project",
        "url": "",
        "geography": "county → CoC",
        "kind": "manual",
        "optional": True,
        "required_if": "hud_pit",
        "files": [MANUAL / "coc_county_crosswalk.csv"],
        "columns": {"coc_county_crosswalk.csv": ["county_fips", "coc_code", "coc_name"]},
        "used_for": "Validation",
    },
    {
        "id": "boundaries",
        "name": "Cartographic boundary files (2020, 1:500k)",
        "publisher": "U.S. Census Bureau",
        "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html",
        "geography": "county + tract",
        "kind": "scripted",
        "fetched_by": "05_build_geo.py",
        "optional": False,
        "files": [RAW / "cb_2020_us_county_500k.zip", RAW / "cb_2020_37_tract_500k.zip"],
        "columns": {},
        "used_for": "Map",
    },
]

# ---------------------------------------------------------------------------
# Index weights (spec §4.4, minus the Help-seeking pillar, removed because no 211 data was
# available). The four pillar weights keep their original values and add up to 85; scores
# use each pillar's share of that total (30/85 ≈ 35%, and so on). Indicator weights inside a
# pillar add up to that pillar's weight.
# ---------------------------------------------------------------------------
PILLARS = {
    "A": {"label": "Displacement pressure", "weight": 30},
    "B": {"label": "Housing cost pressure", "weight": 25},
    "C": {"label": "Economic shock", "weight": 20},
    "D": {"label": "Structural vulnerability", "weight": 10},
}

INDICATOR_WEIGHTS = {
    "eviction_rate": {"pillar": "A", "weight": 20},
    "foreclosure_rate": {"pillar": "A", "weight": 5},
    "eviction_change": {"pillar": "A", "weight": 5},
    "severe_rent_burden": {"pillar": "B", "weight": 12},
    "housing_wage_gap": {"pillar": "B", "weight": 8},
    "rent_growth": {"pillar": "B", "weight": 5},
    "unemployment_rate": {"pillar": "C", "weight": 10},
    "unemployment_change": {"pillar": "C", "weight": 10},
    "poverty_rate": {"pillar": "D", "weight": 4},
    "renter_share": {"pillar": "D", "weight": 2},
    "svi_household": {"pillar": "D", "weight": 2},
    "svi_housing_transport": {"pillar": "D", "weight": 2},
}

# How each indicator is named and shown. "short" is used in tight spots like the watchlist.
#   decimals: rounding for display; signed: show "+" for increases (change indicators)
INDICATOR_INFO = {
    "eviction_rate":         {"label": "Eviction filings", "short": "Evictions", "unit": "per 100 renter households", "decimals": 1},
    "foreclosure_rate":      {"label": "Foreclosure filings", "short": "Foreclosures", "unit": "per 1,000 owner households", "decimals": 1},
    "eviction_change":       {"label": "Change in eviction filings", "short": "Eviction change", "unit": "per 100 renter households", "decimals": 1, "signed": True},
    "severe_rent_burden":    {"label": "Renters paying 50%+ of income on rent", "short": "Rent burden", "unit": "% of renters paying ≥50% of income", "decimals": 1},
    "housing_wage_gap":      {"label": "Housing wage gap", "short": "Housing wage gap", "unit": "ratio (>1 = typical renter can't afford a 2-bedroom)", "decimals": 2},
    "rent_growth":           {"label": "Rent growth", "short": "Rent growth", "unit": "% change in 12 months", "decimals": 1, "signed": True},
    "unemployment_rate":     {"label": "Unemployment rate", "short": "Unemployment", "unit": "%", "decimals": 1},
    "unemployment_change":   {"label": "Change in unemployment", "short": "Unemployment change", "unit": "percentage points", "decimals": 1, "signed": True},
    "poverty_rate":          {"label": "Poverty rate", "short": "Poverty", "unit": "%", "decimals": 1},
    "renter_share":          {"label": "Households that rent", "short": "Renter share", "unit": "% of households", "decimals": 1},
    "svi_household":         {"label": "SVI household characteristics", "short": "SVI household", "unit": "percentile", "decimals": 0},
    "svi_housing_transport": {"label": "SVI housing type & transportation", "short": "SVI housing/transport", "unit": "percentile", "decimals": 0},
    "foreclosure_change":    {"label": "Change in foreclosure filings", "short": "Foreclosure change", "unit": "per 1,000 owner households", "decimals": 1, "signed": True},
}

MOMENTUM_WEIGHTS = {
    "unemployment_change": 35,
    "eviction_change": 25,
    "foreclosure_change": 20,
}

TIERS = [
    {"name": "Low", "min": 0, "max": 20},
    {"name": "Guarded", "min": 20, "max": 40},
    {"name": "Elevated", "min": 40, "max": 60},
    {"name": "High", "min": 60, "max": 80},
    {"name": "Priority", "min": 80, "max": 100},
]

RISING_MOMENTUM_MIN = 75
RISING_SCORE_MIN = 40
LOW_RELIABILITY_POPULATION = 10_000
PARTIAL_DATA_COVERAGE = 0.70
