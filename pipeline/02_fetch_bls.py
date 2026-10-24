"""Step 02: download monthly county unemployment rates from the BLS LAUS program.

Writes pipeline/raw/bls_laus.csv with one row per county per month (last 25 months)
and bls_laus_raw.json (the untouched API responses, for auditing).
County LAUS rates are NOT seasonally adjusted, so later steps compare like months.
"""
import json
from datetime import date

import pandas as pd
import requests

import config
from helpers import read_acs, require_env


def request_batch(series_ids, start_year, end_year, key):
    payload = {
        "seriesid": series_ids,
        "startyear": str(start_year),
        "endyear": str(end_year),
        "registrationkey": key,
    }
    resp = requests.post(config.BLS_URL, json=payload, timeout=120)
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != "REQUEST_SUCCEEDED":
        raise SystemExit(f"BLS API error: {body.get('message')}")
    return body


def main():
    key = require_env("BLS_API_KEY")
    fips_list = sorted(read_acs("county")["fips"])
    series = [config.bls_series_id(f) for f in fips_list]

    # Three calendar years always covers the latest 25 months.
    end_year = date.today().year
    start_year = end_year - 2

    responses, rows = [], []
    for i in range(0, len(series), config.BLS_SERIES_PER_REQUEST):
        batch = series[i : i + config.BLS_SERIES_PER_REQUEST]
        body = request_batch(batch, start_year, end_year, key)
        responses.append(body)
        for s in body["Results"]["series"]:
            fips = s["seriesID"][5:10]
            for d in s["data"]:
                if not d["period"].startswith("M") or d["period"] == "M13":  # M13 = annual average
                    continue
                rows.append({
                    "fips": fips,
                    "month": f"{d['year']}-{d['period'][1:]}",
                    "rate": d["value"],
                    "footnotes": "; ".join(f.get("text", "") for f in d.get("footnotes", []) if f),
                })

    df = pd.DataFrame(rows)
    # BLS writes "-" for months it could not estimate; keep those as missing, never zero.
    df["rate"] = pd.to_numeric(df["rate"], errors="coerce")

    missing_series = set(fips_list) - set(df["fips"])
    if missing_series:
        raise SystemExit(f"BLS returned no data for counties: {sorted(missing_series)}")

    # Keep the latest 25 calendar months (counting gaps, so a skipped month isn't silently replaced).
    latest = pd.Period(df["month"].max(), freq="M")
    keep = {str(latest - i) for i in range(config.BLS_MONTHS)}
    df = df[df["month"].isin(keep)].sort_values(["fips", "month"])

    config.RAW.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.RAW / "bls_laus.csv", index=False)
    (config.RAW / "bls_laus_raw.json").write_text(json.dumps(responses))

    months_present = sorted(df["month"].unique())
    missing_months = sorted(keep - set(months_present))
    print(f"BLS LAUS: {df['fips'].nunique()} counties, {months_present[0]} to {months_present[-1]}.")
    print(f"Latest month: {latest}. Months with no data at all: {missing_months or 'none'}.")
    print(f"County-months with a missing rate: {int(df['rate'].isna().sum())}.")


if __name__ == "__main__":
    main()
