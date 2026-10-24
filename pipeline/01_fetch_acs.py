"""Step 01: download ACS 5-year estimates for NC counties and Durham tracts.

Writes pipeline/raw/acs_county.csv, acs_tract.csv and acs_meta.json (which year was used).
Values are saved exactly as the API returns them; helpers.read_acs() cleans them.
"""
import json
from datetime import datetime, timezone

import pandas as pd
import requests

import config
from helpers import require_env

API = "https://api.census.gov/data/{year}/acs/acs5"


def fetch(year: int, geo_for: str, geo_in: str, key: str) -> pd.DataFrame | None:
    """One API call. Returns None if that ACS year isn't published yet."""
    params = {
        "get": "NAME," + ",".join(config.ACS_VARIABLES),
        "for": geo_for,
        "in": geo_in,
        "key": key,
    }
    resp = requests.get(API.format(year=year), params=params, timeout=60)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    try:
        rows = resp.json()
    except ValueError:
        # The Census API answers some errors (e.g. a year not released yet) with an HTML page.
        return None
    return pd.DataFrame(rows[1:], columns=rows[0]).rename(columns=config.ACS_VARIABLES)


def main():
    key = require_env("CENSUS_API_KEY")

    for year in config.ACS_YEARS_TO_TRY:
        county = fetch(year, "county:*", f"state:{config.STATE_FIPS}", key)
        if county is not None:
            break
        print(f"ACS {year} 5-year not available, trying an earlier year...")
    else:
        raise SystemExit(f"No ACS 5-year release found for any of {config.ACS_YEARS_TO_TRY}.")

    tract = fetch(year, "tract:*", f"state:{config.STATE_FIPS} county:{config.DURHAM_FIPS[2:]}", key)
    if tract is None:
        raise SystemExit(f"ACS {year} served counties but not Durham tracts.")

    county["fips"] = county["state"] + county["county"]
    tract["geoid"] = tract["state"] + tract["county"] + tract["tract"]

    if len(county) != config.N_COUNTIES:
        raise SystemExit(f"Expected {config.N_COUNTIES} NC counties from ACS, got {len(county)}.")

    config.RAW.mkdir(parents=True, exist_ok=True)
    county.to_csv(config.RAW / "acs_county.csv", index=False)
    tract.to_csv(config.RAW / "acs_tract.csv", index=False)
    meta = {
        "acs_year": f"{year - 4}-{year}",
        "end_year": year,
        "retrieved": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (config.RAW / "acs_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"Used ACS {meta['acs_year']} 5-year: {len(county)} counties, {len(tract)} Durham tracts.")


if __name__ == "__main__":
    main()
