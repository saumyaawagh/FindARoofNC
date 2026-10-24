"""Step 03: turn the NC court spreadsheets into one clean county table.

Writes pipeline/interim/courts_county.csv (one row per county) and courts_meta.json with:
  evictions_prev_fy, evictions_latest_fy   summary ejectment filings in each fiscal year
  foreclosures_12m                         filings in the latest 12 months with data
  foreclosures_3m, foreclosures_3m_prev    latest 3 months, and the same 3 months a year earlier
"""
import json
import re
import warnings

import openpyxl
import pandas as pd

import config
from helpers import county_name_to_fips, require_file

warnings.filterwarnings("ignore", module="openpyxl")

MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
CIVIL_FILES = ["civil_issues_fy24-25.xlsx", "civil_issues_fy25-26.xlsx"]
FORECLOSURE_FILES = ["foreclosures_2024.xlsx", "foreclosures_2025.xlsx"]


def is_statewide(names: pd.Series) -> pd.Series:
    # Both file types include a whole-state row next to the 100 counties.
    return names.str.upper().isin(["STATEWIDE", "NORTH CAROLINA"])


def load_evictions(filename: str):
    """Summary ejectment filings per county for one fiscal year. Returns (label, Series by FIPS)."""
    path = require_file(config.MANUAL / filename, "NC courts civil issue filings spreadsheet")
    df = pd.read_excel(path, sheet_name=config.CIVIL_SHEET, dtype={"County": str, "Issue_Code": str})

    # Read the fiscal year from the dates inside the file, never from its name.
    start, end = pd.to_datetime(df["From_"]).min(), pd.to_datetime(df["To_"]).max()
    label = f"FY {start.year}-{str(end.year)[2:]}"

    sume = df[df["Issue_Code"].isin(config.EVICTION_ISSUE_CODES)]
    statewide_total = sume.loc[is_statewide(sume["County"]), "Total_Cases_Filed"].sum()
    counties = sume[~is_statewide(sume["County"])]
    by_county = counties.groupby("County")["Total_Cases_Filed"].sum()

    # The county rows must add up to the file's own statewide row.
    if by_county.sum() != statewide_total:
        raise ValueError(f"{filename}: counties sum to {by_county.sum()}, statewide row says {statewide_total}")

    fips = county_name_to_fips(by_county.index)  # fails unless all 100 counties appear exactly once
    by_county.index = by_county.index.map(fips)
    print(f"Evictions {label}: {int(by_county.sum()):,} summary ejectment filings in {len(by_county)} counties.")
    return label, start, end, by_county


def load_foreclosures():
    """Monthly foreclosure filings per county from the newest foreclosure file."""
    # Each file holds ~20 years of history, so the newest one already contains the older year.
    path = require_file(config.MANUAL / FORECLOSURE_FILES[-1], "NC courts foreclosure filings spreadsheet")

    # The title row says how far the data runs, e.g. "... THROUGH December 31, 2025, ..."
    title = next(openpyxl.load_workbook(path, read_only=True)[config.FORECLOSURE_SHEET].iter_rows(max_row=1, values_only=True))[0]
    through = pd.to_datetime(re.search(r"THROUGH (\w+ \d+, \d{4})", title).group(1))

    df = pd.read_excel(path, sheet_name=config.FORECLOSURE_SHEET, header=1, dtype={"County": str})
    df = df[~is_statewide(df["County"])]
    long = df.melt(id_vars=["County", "Year"], value_vars=MONTHS, var_name="month_name", value_name="filings")
    long["month"] = pd.to_datetime(long["Year"].astype(str) + "-" + long["month_name"], format="%Y-%B").dt.to_period("M")

    latest = through.to_period("M")
    long = long[long["month"] <= latest]
    if long.loc[long["month"] == latest, "filings"].isna().any():
        raise ValueError(f"{path.name}: some counties have no value for {latest}")

    wide = long.pivot_table(index="County", columns="month", values="filings", aggfunc="sum")
    last_12 = [latest - i for i in range(12)]
    last_3 = [latest - i for i in range(3)]
    prev_3 = [m - 12 for m in last_3]

    out = pd.DataFrame({
        "foreclosures_12m": wide[last_12].sum(axis=1),
        "foreclosures_3m": wide[last_3].sum(axis=1),
        "foreclosures_3m_prev": wide[prev_3].sum(axis=1),
    })
    out.index = out.index.map(county_name_to_fips(out.index))
    print(f"Foreclosures: latest month with data is {latest} (file says through {through:%B %d, %Y}).")
    meta = {
        "foreclosure_latest_month": str(latest),
        "foreclosure_12m_window": f"{last_12[-1]} to {latest}",
        "foreclosure_3m_window": f"{last_3[-1]} to {latest}",
        "foreclosure_3m_prev_window": f"{prev_3[-1]} to {prev_3[0]}",
    }
    return out, meta


def main():
    years = sorted((load_evictions(f) for f in CIVIL_FILES), key=lambda r: r[1])
    (prev_label, *_, prev), (latest_label, _, latest_end, latest) = years

    foreclosures, meta = load_foreclosures()

    table = pd.DataFrame({"evictions_prev_fy": prev, "evictions_latest_fy": latest}).join(foreclosures)
    table.index.name = "fips"
    if len(table) != config.N_COUNTIES or table.isna().any().any():
        raise ValueError("courts table should have 100 complete county rows")

    config.INTERIM.mkdir(parents=True, exist_ok=True)
    table.reset_index().to_csv(config.INTERIM / "courts_county.csv", index=False)
    meta.update({"eviction_prev_fy": prev_label, "eviction_latest_fy": latest_label,
                 "eviction_latest_fy_end": f"{latest_end:%Y-%m-%d}"})
    (config.INTERIM / "courts_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"Wrote courts_county.csv ({len(table)} counties).")


if __name__ == "__main__":
    main()
