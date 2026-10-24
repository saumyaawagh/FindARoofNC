"""Step 04: clean the remaining sources into small tables in pipeline/interim/.

  fmr_county.csv              HUD 2-bedroom Fair Market Rent per county
  svi_county.csv, svi_tract.csv   SVI themes 2 and 4 (state-based percentiles, 0–1)
  durham_evictions_tract.csv  Compass summary ejectments moved onto 2020 tracts
  zori_county.csv             (optional) Zillow rent index, latest and 12 months earlier
  other_meta.json             vintages and notes for the Methods page
"""
import json
import warnings

import numpy as np
import pandas as pd
import requests

import config
from helpers import read_acs, require_file

warnings.filterwarnings("ignore", module="openpyxl")

COMPASS = config.RAW / "durham-quality-of-life-data"
REL_FILE = config.RAW / "tab20_blkgrp20_blkgrp10_natl.txt"


def source(source_id):
    return next(s for s in config.SOURCES if s["id"] == source_id)


def load_fmr():
    path = require_file(config.MANUAL / "fmr_2027.xlsx", "HUD FY2027 county Fair Market Rents")
    df = pd.read_excel(path, sheet_name="FY27_FMRs", dtype={"fips": str})
    nc = df[df["stusps"] == "NC"].copy()
    # HUD's 10-digit code = 5-digit county FIPS + "99999" (a New England town code we don't need).
    nc["fips"] = nc["fips"].str[:5]
    out = nc[["fips", "fmr_2"]]
    if out["fips"].nunique() != config.N_COUNTIES or out["fmr_2"].isna().any():
        raise ValueError(f"{path.name}: expected one 2-bedroom FMR for each of the 100 NC counties")
    return out


def load_svi(geo):
    name = f"svi_2022_nc_{geo}.csv"
    path = require_file(config.MANUAL / name, f"CDC SVI 2022 NC {geo} CSV")
    df = pd.read_csv(path, dtype={"FIPS": str}, usecols=["FIPS", "RPL_THEME2", "RPL_THEME4"], encoding="utf-8-sig")
    df = df.replace(config.SVI_MISSING, np.nan)
    if geo == "tract":
        df = df[df["FIPS"].str.startswith(config.DURHAM_FIPS)]
    return df.rename(columns={"FIPS": "fips" if geo == "county" else "geoid"})


def download_relationship_file():
    if REL_FILE.exists():
        return
    url = source("blockgroup_crosswalk")["url"]
    print(f"Downloading {url} ...")
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()
    REL_FILE.write_bytes(resp.content)


def load_durham_evictions():
    """Move the Compass's 2010 block-group eviction counts onto 2020 tracts.

    A 2010 block group's count is split across the 2020 block groups it overlaps, in
    proportion to shared land area, then summed up to 2020 tracts (first 11 digits).
    Block groups whose boundaries didn't change pass through with (almost) their full count.
    """
    path = require_file(COMPASS / "metric" / "blockgroup" / "sumeject_numerator.csv",
                        "Compass block-group summary ejectment counts (git clone, see manual/README.md)")
    counts = pd.read_csv(path, dtype={"fips": str})
    # Latest year in which every block group has a value.
    complete = counts.groupby("year")["value"].apply(lambda v: v.notna().all())
    year = int(complete[complete].index.max())
    counts = counts[counts["year"] == year].rename(columns={"fips": "bg10", "value": "evictions"})

    download_relationship_file()
    rel = pd.read_csv(REL_FILE, sep="|", dtype=str, encoding="utf-8-sig",
                      usecols=["GEOID_BLKGRP_20", "GEOID_BLKGRP_10", "AREALAND_BLKGRP_10", "AREALAND_PART"])
    rel = rel[rel["GEOID_BLKGRP_10"].str.startswith(config.DURHAM_FIPS)].copy()
    rel["share"] = rel["AREALAND_PART"].astype(float) / rel["AREALAND_BLKGRP_10"].astype(float)

    unknown = set(counts["bg10"]) - set(rel["GEOID_BLKGRP_10"])
    if unknown:
        raise ValueError(f"Compass block groups not in the Census 2010 list: {sorted(unknown)[:5]}")

    merged = counts.merge(rel, left_on="bg10", right_on="GEOID_BLKGRP_10")
    merged["allocated"] = merged["evictions"] * merged["share"]
    merged["geoid"] = merged["GEOID_BLKGRP_20"].str[:11]

    in_durham = merged["geoid"].str.startswith(config.DURHAM_FIPS)
    lost = merged.loc[~in_durham, "allocated"].sum()
    tracts = merged[in_durham].groupby("geoid")["allocated"].sum().rename("evictions").reset_index()

    # Check: for tracts whose ID didn't change since 2010, our crosswalked count should be
    # close to the Compass's own tract count (small gaps come from 2020 boundary nudges).
    compass_tracts = pd.read_csv(COMPASS / "metric" / "tract" / "sumeject_numerator.csv", dtype={"fips": str})
    compass_tracts = compass_tracts[compass_tracts["year"] == year].set_index("fips")["value"]
    tracts["same_id_as_2010"] = tracts["geoid"].isin(compass_tracts.index)
    same = tracts[tracts["same_id_as_2010"]].set_index("geoid")["evictions"]
    gap = (same - compass_tracts.reindex(same.index)).abs()

    total = counts["evictions"].sum()
    print(f"Durham Compass {year}: {total:,.0f} summary ejectments in {len(counts)} block groups (2010) "
          f"-> {len(tracts)} tracts (2020); {lost:.1f} fell outside Durham County.")
    print(f"  {len(same)} tracts kept their 2010 ID; crosswalked vs Compass tract counts differ by "
          f"{gap.mean():.1f} filings on average (max {gap.max():.1f}).")
    return tracts, year


def load_zori():
    """Optional. Latest Zillow rent index and the value 12 months earlier, per NC county."""
    path = config.MANUAL / "zori_county.csv"
    if not path.exists():
        return None, None
    df = pd.read_csv(path, dtype={"StateCodeFIPS": str, "MunicipalCodeFIPS": str})
    df = df[df["StateName"] == "NC"].copy()
    df["fips"] = df["StateCodeFIPS"].str.zfill(2) + df["MunicipalCodeFIPS"].str.zfill(3)
    month_cols = sorted(c for c in df.columns if c[:2] in ("19", "20") and c[4] == "-")
    latest_col = next(c for c in reversed(month_cols) if df[c].notna().any())
    prev_col = month_cols[month_cols.index(latest_col) - 12]
    out = df[["fips"]].assign(zori_latest=df[latest_col], zori_prev=df[prev_col])
    return out.dropna(), f"{prev_col[:7]} to {latest_col[:7]}"


def main():
    config.INTERIM.mkdir(parents=True, exist_ok=True)
    meta = {}

    load_fmr().to_csv(config.INTERIM / "fmr_county.csv", index=False)
    print("FMR: 100 counties (FY2027 2-bedroom).")

    load_svi("county").to_csv(config.INTERIM / "svi_county.csv", index=False)
    svi_tract = load_svi("tract")
    svi_tract.to_csv(config.INTERIM / "svi_tract.csv", index=False)
    print(f"SVI 2022: 100 counties, {len(svi_tract)} Durham tracts.")

    tracts, year = load_durham_evictions()
    acs_tracts = set(read_acs("tract")["geoid"])
    missing = acs_tracts - set(tracts["geoid"])
    if missing:
        print(f"  Note: {len(missing)} ACS tracts got no Compass block group: {sorted(missing)}")
    tracts.to_csv(config.INTERIM / "durham_evictions_tract.csv", index=False)
    meta["durham_eviction_year"] = year

    zori, window = load_zori()
    if zori is not None:
        zori.to_csv(config.INTERIM / "zori_county.csv", index=False)
        meta["zori_window"] = window
        print(f"ZORI: {len(zori)} counties, {window}.")
    else:
        (config.INTERIM / "zori_county.csv").unlink(missing_ok=True)
        print("ZORI: optional, not present.")

    if (config.MANUAL / "211_county.csv").exists():
        # The 211 export format hasn't been seen yet, so there's no loader to trust.
        raise SystemExit("211_county.csv is present, but its loader hasn't been written yet. "
                         "Ask Claude to inspect the export and add it to 04_load_other.py.")
    print("NC 211: optional, not present.")

    (config.INTERIM / "other_meta.json").write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
