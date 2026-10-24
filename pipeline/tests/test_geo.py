"""Map shapes are light enough, in the right coordinate system, and join to the index."""
import json

import pandas as pd
import pytest

import config

FILES = [
    ("nc_counties.geojson", 400, "fips", "index_counties.json", 100),
    ("durham_tracts.geojson", 300, "geoid", "index_tracts.json", 68),
]


@pytest.mark.parametrize("name,budget_kb,id_field,index_file,count", FILES)
def test_geojson(name, budget_kb, id_field, index_file, count):
    path = config.SITE_DATA / name
    assert path.stat().st_size <= budget_kb * 1024, f"{name} is over {budget_kb} KB"

    features = json.loads(path.read_text())["features"]
    assert len(features) == count
    assert all(set(f["properties"]) == {id_field, "name"} for f in features)

    # EPSG:4326 check: every longitude/latitude sits inside North Carolina.
    def coords(geom):
        rings = geom["coordinates"] if geom["type"] == "Polygon" else [r for p in geom["coordinates"] for r in p]
        return [pt for ring in rings for pt in ring]

    points = [pt for f in features for pt in coords(f["geometry"])]
    assert all(-84.4 <= lon <= -75.4 and 33.8 <= lat <= 36.6 for lon, lat in points)

    # Every shape has a matching scored unit (joined by ID, never by name).
    index_ids = {u[id_field] for u in json.loads((config.INTERIM / index_file).read_text())}
    assert {f["properties"][id_field] for f in features} == index_ids


def test_tract_names_match_between_map_and_index():
    # Both come from helpers.tract_display_name, so the tooltip, panel and CSV agree.
    shapes = json.loads((config.SITE_DATA / "durham_tracts.geojson").read_text())["features"]
    on_map = {f["properties"]["geoid"]: f["properties"]["name"] for f in shapes}
    in_index = {u["geoid"]: u["name"] for u in json.loads((config.INTERIM / "index_tracts.json").read_text())}
    assert on_map == in_index


def test_tract_names_have_neighborhood_labels():
    table = pd.read_csv(config.INTERIM / "tract_neighborhoods.csv", dtype={"geoid": str})
    hoods = dict(zip(table["geoid"], table["neighborhood"].fillna("")))
    names = {u["geoid"]: u["name"] for u in json.loads((config.INTERIM / "index_tracts.json").read_text())}
    for geoid, name in names.items():
        assert name.startswith("Tract ")
        if hoods.get(geoid):
            assert name.endswith(f" · {hoods[geoid]} area"), name
        else:
            assert " · " not in name
    assert names["37063000301"] == "Tract 3.01 · Walltown area"
