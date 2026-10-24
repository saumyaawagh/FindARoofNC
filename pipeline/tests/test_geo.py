"""Map shapes are light enough, in the right coordinate system, and join to the index."""
import json

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
