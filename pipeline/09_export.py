"""Step 09: write the JSON files the website reads (data contracts, spec §5).

  site/src/data/counties.json        meta + 100 county units (with unemployment sparkline)
  site/src/data/durham_tracts.json   meta + 68 Durham tract units (no momentum fields)
  site/src/data/validation.json      copied from 07_validate.py
  site/src/data/sources.json         every source, its data year, and whether it was used
(nc_counties.geojson and durham_tracts.geojson are written by 05_build_geo.py;
 briefs.json by 08_briefs.py.)
"""
import json
from datetime import date, datetime, timezone

import pandas as pd

import config

SPARKLINE_MONTHS = 24


def read_interim(name):
    path = config.INTERIM / name
    if not path.exists():
        raise FileNotFoundError(f"Missing {path.relative_to(config.ROOT)}: run the earlier pipeline steps first.")
    return json.loads(path.read_text())


def write(name, data):
    path = config.SITE_DATA / name
    path.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    print(f"Wrote {name}: {path.stat().st_size / 1024:.0f} KB")


def unemployment_series():
    """Last 24 months of the unemployment rate per county. Months BLS didn't publish stay null."""
    bls = pd.read_csv(config.RAW / "bls_laus.csv", dtype={"fips": str})
    months = sorted(bls["month"].unique())[-SPARKLINE_MONTHS:]
    bls = bls[bls["month"].isin(months)]
    series = {}
    for fips, rows in bls.groupby("fips"):
        series[fips] = [{"month": m, "rate": None if pd.isna(r) else float(r)}
                        for m, r in zip(rows["month"], rows["rate"])]
    return series


def build_meta(peers, missing_optional, acs_meta, data_as_of):
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "acs_year": acs_meta["acs_year"],
        "peers": peers,
        "pillars": config.PILLARS,
        "indicator_weights": config.INDICATOR_WEIGHTS,
        "indicator_info": config.INDICATOR_INFO,
        "momentum_weights": config.MOMENTUM_WEIGHTS,
        "tiers": config.TIERS,
        "missing_optional_sources": missing_optional,
        "data_as_of": data_as_of,
    }


def file_date(paths):
    """When a file was saved locally, used as its 'retrieved' date."""
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    return date.fromtimestamp(max(p.stat().st_mtime for p in existing)).isoformat()


def build_sources(acs_meta, courts_meta, other_meta, bls_range, missing_optional):
    vintages = {
        "acs": f"{acs_meta['acs_year']} 5-year",
        "bls_laus": bls_range,
        "hud_fmr": "FY2027",
        "nc_evictions": f"{courts_meta['eviction_prev_fy']} and {courts_meta['eviction_latest_fy']}",
        "nc_foreclosures": f"Monthly through {pd.Period(courts_meta['foreclosure_latest_month']).strftime('%b %Y')}",
        "svi": "2022",
        "durham_compass": f"{other_meta['durham_eviction_year']} (2010 tract geography)",
        "blockgroup_crosswalk": "2020 ↔ 2010",
        "boundaries": "2020",
    }
    sources = []
    for s in config.SOURCES:
        present = all(p.exists() for p in s["files"])
        if s["id"] == "acs":
            retrieved = acs_meta["retrieved"][:10]
        else:
            retrieved = file_date(s["files"])
        sources.append({
            "id": s["id"],
            "name": s["name"],
            "publisher": s["publisher"],
            "url": s["url"],
            "geography": s["geography"],
            "vintage": vintages.get(s["id"]) if present else None,
            "retrieved": retrieved if present else None,
            "used_for": s["used_for"],
            "status": "used" if present else "missing-optional",
        })
        if not present and not s["optional"]:
            raise ValueError(f"Required source {s['id']} is missing; run 00_check_raw.py")
    return sources


def main():
    counties = read_interim("index_counties.json")
    tracts = read_interim("index_tracts.json")
    index_meta = read_interim("index_meta.json")
    validation = read_interim("validation.json")
    courts_meta = read_interim("courts_meta.json")
    other_meta = read_interim("other_meta.json")
    acs_meta = json.loads((config.RAW / "acs_meta.json").read_text())

    series = unemployment_series()
    for u in counties:
        u["unemployment_series"] = series[u["fips"]]
    months = [p["month"] for p in counties[0]["unemployment_series"]]
    month_label = lambda m: pd.Period(m, freq="M").strftime("%b %Y")
    bls_range = f"{month_label(months[0])} – {month_label(months[-1])} (monthly)"

    # Shown in the header ("Data as of …") and the panel's freshness list.
    data_as_of = {
        "unemployment": month_label(months[-1]),
        "evictions": courts_meta["eviction_latest_fy"],
        "foreclosures": month_label(courts_meta["foreclosure_latest_month"]),
        "acs": acs_meta["acs_year"],
        "fair_market_rent": "FY2027",
        "svi": "2022",
        "durham_evictions": str(other_meta["durham_eviction_year"]),
    }
    missing_optional = index_meta["missing_optional_sources"]

    config.SITE_DATA.mkdir(parents=True, exist_ok=True)
    write("counties.json", {"meta": build_meta("NC counties", missing_optional, acs_meta, data_as_of),
                            "units": counties})
    write("durham_tracts.json", {"meta": build_meta("Durham County tracts", missing_optional, acs_meta, data_as_of),
                                 "units": tracts})
    write("validation.json", validation)
    write("sources.json", build_sources(acs_meta, courts_meta, other_meta, bls_range, missing_optional))

    total = sum(p.stat().st_size for p in config.SITE_DATA.iterdir() if p.is_file())
    print(f"Total site data: {total / 1024:.0f} KB")


if __name__ == "__main__":
    main()
