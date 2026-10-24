"""Step 05: build the two map shapes the site needs.

Downloads Census 2020 cartographic boundaries (1:500k) and writes:
  site/src/data/nc_counties.geojson    properties {fips, name}       budget 400 KB
  site/src/data/durham_tracts.geojson  properties {geoid, name}      budget 300 KB
Coordinates are WGS84 (EPSG:4326, what web maps expect), simplified and rounded to 5 decimals.

Also writes pipeline/interim/tract_neighborhoods.csv: for each Durham tract, the Durham
Neighborhood Compass neighborhood that covers the largest share of it, so tracts can be shown
as "Tract 3.01 · Walltown area".
"""
import json

import geopandas as gpd
import numpy as np
import requests
import shapely

import config
from helpers import require_file, tract_display_name

BASE = "https://www2.census.gov/geo/tiger/GENZ2020/shp/"
COUNTY_ZIP = config.RAW / "cb_2020_us_county_500k.zip"
TRACT_ZIP = config.RAW / "cb_2020_37_tract_500k.zip"

# Simplification tolerance in degrees (0.001° is roughly 100 m). Small enough to look right
# at the zoom levels we allow, large enough to keep the files light.
COUNTY_TOLERANCE = 0.002
TRACT_TOLERANCE = 0.0004
BUDGET_KB = {"nc_counties.geojson": 400, "durham_tracts.geojson": 300}
NEIGHBORHOODS = config.RAW / "durham-quality-of-life-data" / "selectgroups.geojson.json"
NC_STATE_PLANE = 32119  # a flat projection in meters, so areas are measured correctly


def download(path):
    if path.exists():
        return
    print(f"Downloading {path.name} ...")
    resp = requests.get(BASE + path.name, timeout=300)
    resp.raise_for_status()
    path.write_bytes(resp.content)


def simplify(gdf, tolerance):
    gdf = gdf.to_crs(4326)
    # simplify_coverage treats the polygons as one connected mesh, so neighbours still share
    # exactly the same edge afterwards (no gaps or overlaps between counties).
    gdf["geometry"] = gdf.geometry.simplify_coverage(tolerance)
    gdf["geometry"] = shapely.transform(gdf.geometry.values, lambda xy: np.round(xy, 5))
    return gdf


def write_geojson(gdf, name):
    data = json.loads(gdf.to_json(drop_id=True))
    out = config.SITE_DATA / name
    out.write_text(json.dumps(data, separators=(",", ":")))
    size_kb = out.stat().st_size / 1024
    print(f"Wrote {name}: {len(gdf)} features, {size_kb:.0f} KB (budget {BUDGET_KB[name]} KB).")
    if size_kb > BUDGET_KB[name]:
        raise ValueError(f"{name} is over its size budget; raise its tolerance in 05_build_geo.py")


def tract_neighborhoods(tracts):
    """For each tract, the neighborhood covering the largest share of its area.

    Every tract that touches a neighborhood gets one, even if the share is small (the
    builder's choice); the share is kept in the table so it can be checked.
    """
    path = require_file(NEIGHBORHOODS, "Durham Neighborhood Compass select groups (git clone, see manual/README.md)")
    hoods = gpd.read_file(path)
    hoods = hoods[hoods["feature_type"] == "neighborhood"][["id", "geometry"]].to_crs(NC_STATE_PLANE)
    hoods["geometry"] = hoods.geometry.make_valid()

    t = tracts[["geoid", "geometry"]].to_crs(NC_STATE_PLANE)
    t["tract_area"] = t.area
    pieces = gpd.overlay(t, hoods, how="intersection", keep_geom_type=True)
    pieces["share"] = pieces.area / pieces["tract_area"]
    best = pieces.sort_values("share", ascending=False).drop_duplicates("geoid").set_index("geoid")

    table = t[["geoid"]].copy()
    table["neighborhood"] = table["geoid"].map(best["id"])
    table["share"] = table["geoid"].map(best["share"]).round(4)
    labelled = table["neighborhood"].notna().sum()
    print(f"Neighborhood labels: {labelled} of {len(table)} tracts "
          f"(median share of tract covered: {table['share'].median():.0%}).")
    return table


def main():
    config.RAW.mkdir(parents=True, exist_ok=True)
    config.SITE_DATA.mkdir(parents=True, exist_ok=True)
    download(COUNTY_ZIP)
    download(TRACT_ZIP)

    counties = gpd.read_file(f"zip://{COUNTY_ZIP}")
    counties = counties[counties["STATEFP"] == config.STATE_FIPS]
    if len(counties) != config.N_COUNTIES:
        raise ValueError(f"Expected 100 NC counties in {COUNTY_ZIP.name}, found {len(counties)}")
    counties = counties.rename(columns={"GEOID": "fips", "NAME": "name"})[["fips", "name", "geometry"]]
    write_geojson(simplify(counties.sort_values("fips"), COUNTY_TOLERANCE), "nc_counties.geojson")

    tracts = gpd.read_file(f"zip://{TRACT_ZIP}")
    tracts = tracts[tracts["GEOID"].str.startswith(config.DURHAM_FIPS)].copy()
    tracts = tracts.rename(columns={"GEOID": "geoid"})
    hoods = tract_neighborhoods(tracts)
    config.INTERIM.mkdir(parents=True, exist_ok=True)
    hoods.to_csv(config.INTERIM / "tract_neighborhoods.csv", index=False)
    by_geoid = dict(zip(hoods["geoid"], hoods["neighborhood"]))
    tracts["name"] = [tract_display_name(n, by_geoid.get(g)) for n, g in zip(tracts["NAME"], tracts["geoid"])]
    tracts = tracts[["geoid", "name", "geometry"]]
    write_geojson(simplify(tracts.sort_values("geoid"), TRACT_TOLERANCE), "durham_tracts.geojson")


if __name__ == "__main__":
    main()
