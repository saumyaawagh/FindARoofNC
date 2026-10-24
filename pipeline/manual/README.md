# Manual downloads checklist

Save every file into this folder (`pipeline/manual/`) with **exactly** the name shown, then run:

```bash
.venv/bin/python pipeline/00_check_raw.py
```

Re-run it until every required source is ✅. Optional sources may stay ⚠️: their weight is shared out among the other indicators, and the site says so.

The Census ACS and BLS data come from APIs (`01_fetch_acs.py`, `02_fetch_bls.py`) using the keys in `.env`. Map boundaries are downloaded by `05_build_geo.py`. You don't download those by hand.

---

## Required

### 1. HUD Fair Market Rents → `fmr_2027.xlsx` ✅ have it
- **Where:** https://www.huduser.gov/portal/datasets/fmr.html
- **Click:** the current fiscal year (FY2027) → "County-level data" → Excel file.
- **Expected:** sheet `FY27_FMRs` with columns `stusps`, `fips` (10 digits, first 5 = county FIPS), `countyname`, `fmr_2` (2-bedroom rent).
- **Next year:** when FY2028 comes out, save it as `fmr_2028.xlsx` and update `config.py`.

### 2. NC court civil issue filings → `civil_issues_fy24-25.xlsx`, `civil_issues_fy25-26.xlsx` ✅ have them
- **Where:** https://www.nccourts.gov/documents/publications/civil-issue-filingsorder-results
- **Click:** the spreadsheet for each fiscal year (fiscal years run July–June).
- **Expected:** sheet `VCAP_Issues` with `From_`, `To_`, `County`, `Case_Type`, `Issue_Code`, `Issue_Text`, `Total_Cases_Filed`, and monthly columns (`July_Case_Issue_Filed` …).
- **Name check:** the file name must match the `From_`/`To_` dates inside. `00_check_raw.py` checks this. (The first downloads had their names swapped; they were renamed on 2026-10-24.)
- **Eviction rows:** `Issue_Code = SUME` ("Summary Ejectment"), all case types. Small claims (`CVM`) holds over 99% of these filings.
- These files are 10–12 MB, so they're gitignored. Anyone re-running the pipeline downloads them again.

### 3. NC court foreclosure filings → `foreclosures_2024.xlsx`, `foreclosures_2025.xlsx` ✅ have them
- **Where:** https://www.nccourts.gov/documents/publications/foreclosure-filings
- **Click:** the calendar-year spreadsheet for 2024 and for 2025.
- **Expected:** sheet `FORE`. Row 1 is a title ("… THROUGH December 31, 2025 …"); row 2 holds the headers `County`, `Year`, `All Months`, `January` … `December`.
- Each file holds about 20 years of history, so the newest file also contains the older years.

### 4. CDC/ATSDR Social Vulnerability Index 2022 → `svi_2022_nc_county.csv`, `svi_2022_nc_tract.csv` ✅ have them
- **Where:** https://www.atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html
- **Click:** Year 2022 → Geography: North Carolina → Geography type: Counties (then again for Census Tracts) → File type: CSV. Make sure it is the **state-based** file (ranked within NC), not the U.S.-wide one.
- **Expected:** `FIPS` (5 digits for counties, 11 for tracts), `RPL_THEME2`, `RPL_THEME4`. `-999` means missing.

### 5. Durham Neighborhood Compass data → `pipeline/raw/durham-quality-of-life-data/` ✅ have it
- **How:** from the project root, run:
  ```bash
  git clone --depth 1 https://github.com/DataWorks-NC/durham-quality-of-life-data pipeline/raw/durham-quality-of-life-data
  ```
- **Expected:** `config/data.js` (metric `mSUMEJECT`, "Evictions (Summary Ejectments)") and `metric/blockgroup/sumeject_numerator.csv` plus `metric/tract/sumeject_numerator.csv` with columns `fips`, `year`, `value`.
- Also used: `selectgroups.geojson.json` (neighborhood boundaries), to label each tract with the neighborhood covering most of it, e.g. "Tract 3.01 · Walltown area".
- Use the **numerator** files (raw counts). The Compass website maps filings *per square mile*, which is the wrong unit for us.
- **Geography note:** the Compass uses **2010** tracts and block groups (60 tracts and 153 block groups). Only 52 of its 60 tracts match the 2020 tracts that ACS and SVI use. Its latest year is 2022. The pipeline moves the block-group counts onto 2020 tracts using the Census relationship file (see `METHODS.md`).

---

## Optional (sources)

### 6. NC 211 housing & shelter requests → `211_county.csv`, `211_zip.csv` ⚠️ missing
- **Where:** https://www.nc211.org/data (links to the "211 Counts" dashboard).
- **Click:** filter to the *Housing & Shelter* need category. Pick the last 15 months, group by **county**, and export to CSV. Repeat grouped by **ZIP code**.
- **Expected:** a geography column (county name or ZIP), a date or month column, and a request count. Exact column names will be set once a real export has been inspected.
- If the dashboard has no export button, leave this optional and missing. Pillar D (help-seeking) will then be blank, and its weight is shared out.

### 7. Zillow Observed Rent Index → `zori_county.csv` ⚠️ missing
- **Where:** https://www.zillow.com/research/data/
- **Click:** "Rentals" section → Data type *ZORI (Smoothed): All Homes Plus Multifamily Time Series ($)* → Geography *County* → Download.
- **Expected:** `RegionName`, `StateName`, `StateCodeFIPS`, `MunicipalCodeFIPS`, then one column per month (`2025-09-30`, …). Zillow only covers some counties, mostly metro ones.

## Optional (validation only)

### 8. Homeless students enrolled → `student_homeless_lea.csv` ⚠️ missing
- **Where:** https://eddataexpress.ed.gov/ → Download → Data download tool.
- **Click:** Program *Education for Homeless Children and Youth* → data group "Homeless students enrolled" (EDFacts file 118) → State *North Carolina* → Level *LEA* (school district) → the latest **2** school years → CSV.
- **Needs:** item 9.

### 9. School district → county crosswalk → `lea_county_crosswalk.csv` (hand-built; needed only with item 8)
- **Columns:** `lea_name` (exactly as written in item 8), `county_fips` (5-digit string).
- City school districts (e.g. Asheville City Schools) map to the county they sit in. Claude can draft this from the LEA list once item 8 is downloaded. You then check it.

### 10. HUD Point-in-Time counts by CoC → `pit_by_coc.xlsb` ⚠️ missing
- **Where:** https://www.huduser.gov/portal/datasets/ahar.html → AHAR data files.
- **Click:** "2007–2025 Point-in-Time Estimates by CoC" (.xlsb). Use the 2007–2024 file if 2025 isn't posted.
- **Needs:** item 11.

### 11. County → CoC crosswalk → `coc_county_crosswalk.csv` (hand-built; needed only with item 10)
- **Columns:** `county_fips`, `coc_code` (e.g. `NC-502`), `coc_name`.
- NC has 12 CoCs; the Balance of State CoC (`NC-503`) covers 79 counties. Check every row against HUD's published CoC geography before using it.
