"""Reads the NYC taxi zone boundaries and turns them into one clean geometry per zone.

Supported inputs (first one found in data/ wins):
    data/taxi_zones.geojson   plain GeoJSON, no extra libraries needed
    data/taxi_zones.json      same thing, different extension
    data/taxi_zones.zip       the original TLC shapefile (needs geopandas)
    data/taxi_zones/taxi_zones.shp   the unzipped shapefile (needs geopandas)

Output of load_zone_geometries(): {location_id: (geometry_json_string, centroid_lat, centroid_lng)}
"""
import glob
import json
import os

DATA_DIR = "data"
COORD_DECIMALS = 5          # 5 decimals is about 1 metre, plenty for a city map


# ---------------------------------------------------------------------------
# Finding and reading the file
# ---------------------------------------------------------------------------
def find_zone_file(data_dir=DATA_DIR):
    """Return the path of the first taxi zone file that exists, or None."""
    candidates = [
        os.path.join(data_dir, "taxi_zones.geojson"),
        os.path.join(data_dir, "taxi_zones.json"),
        os.path.join(data_dir, "taxi_zones.zip"),
        os.path.join(data_dir, "taxi_zones", "taxi_zones.shp"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    # Last resort: any .geojson file in the data folder
    found = sorted(glob.glob(os.path.join(data_dir, "*.geojson")))
    return found[0] if found else None


def read_features(path):
    """Return a list of GeoJSON features (dicts) from a GeoJSON file or a shapefile."""
    if path.endswith((".geojson", ".json")):
        with open(path, encoding="utf-8") as f:
            return json.load(f)["features"]

    # Shapefile route: geopandas reads it and converts to the lat/lng system for us
    try:
        import geopandas as gpd
    except ImportError:
        raise SystemExit(
            "Your taxi zone file is a shapefile, which needs geopandas.\n"
            "Run: pip install geopandas   (or use the GeoJSON version of the file)"
        )
    gdf = gpd.read_file(path).to_crs(epsg=4326)
    return json.loads(gdf.to_json())["features"]


# ---------------------------------------------------------------------------
# Coordinate handling
# ---------------------------------------------------------------------------
def _first_point(geometry):
    """Dig down to the very first [x, y] pair of a geometry."""
    coords = geometry["coordinates"]
    while isinstance(coords[0], list):
        coords = coords[0]
    return coords


def looks_projected(features):
    """True if coordinates are too big to be longitude/latitude (e.g. State Plane feet)."""
    x, y = _first_point(features[0]["geometry"])[:2]
    return abs(x) > 180 or abs(y) > 90


def _map_coords(coords, fn):
    """Apply fn to every [x, y] pair in a nested coordinate list."""
    if isinstance(coords[0], (int, float)):
        return fn(coords)
    return [_map_coords(c, fn) for c in coords]


def reproject_to_wgs84(features):
    """Convert State Plane (EPSG:2263, the TLC's original system) to longitude/latitude."""
    try:
        from pyproj import Transformer
    except ImportError:
        raise SystemExit(
            "The zone coordinates are not in longitude/latitude, so they need converting.\n"
            "Run: pip install pyproj   (or use a GeoJSON file that is already in WGS84)"
        )
    print("Zone coordinates look projected; converting from EPSG:2263 to WGS84")
    tf = Transformer.from_crs("EPSG:2263", "EPSG:4326", always_xy=True)

    def convert(pt):
        lng, lat = tf.transform(pt[0], pt[1])
        return [lng, lat]

    for feat in features:
        feat["geometry"]["coordinates"] = _map_coords(feat["geometry"]["coordinates"], convert)
    return features


def _round_coords(coords):
    return _map_coords(
        coords, lambda p: [round(p[0], COORD_DECIMALS), round(p[1], COORD_DECIMALS)])


# ---------------------------------------------------------------------------
# Geometry maths (done by hand, no shapely needed)
# ---------------------------------------------------------------------------
def _ring_area_centroid(ring):
    """Shoelace formula. Returns (area, cx, cy) for one closed ring (area is positive)."""
    a = cx = cy = 0.0
    for i in range(len(ring) - 1):
        x0, y0 = ring[i][0], ring[i][1]
        x1, y1 = ring[i + 1][0], ring[i + 1][1]
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if a == 0:
        return 0.0, 0.0, 0.0
    a /= 2
    return abs(a), cx / (6 * a), cy / (6 * a)


def polygons_of(geometry):
    """Always return a list of polygons, whether the input was a Polygon or MultiPolygon."""
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    return geometry["coordinates"]


def centroid_of(polygons):
    """Area-weighted centroid of a list of polygons; holes count as negative area.
    Returns (lat, lng)."""
    total = sx = sy = 0.0
    for poly in polygons:
        for idx, ring in enumerate(poly):
            area, cx, cy = _ring_area_centroid(ring)
            sign = 1 if idx == 0 else -1          # first ring is the outline, the rest are holes
            total += sign * area
            sx += sign * area * cx
            sy += sign * area * cy
    if total == 0:
        # Degenerate shape: fall back to the plain average of all points
        pts = [p for poly in polygons for ring in poly for p in ring]
        return (sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts))
    return sy / total, sx / total


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def get_location_id(props):
    """Find the zone id in a feature's properties, whatever the column is called.
    OBJECTID is deliberately NOT accepted: it is a row number, not the taxi zone id."""
    for key, val in props.items():
        if key.lower().replace("_", "") == "locationid":
            return int(val)
    raise ValueError(f"No LocationID property found. Properties were: {list(props)}")


def load_zone_geometries(path=None):
    """Return {location_id: (geometry_json, centroid_lat, centroid_lng)}.

    A few zone ids appear on several features (islands split into pieces), so features
    with the same id are merged into one MultiPolygon."""
    path = path or find_zone_file()
    if path is None:
        raise SystemExit(
            "No taxi zone boundary file found in data/.\n"
            "Put taxi_zones.geojson (or the TLC taxi_zones.zip shapefile) in the data folder."
        )
    print(f"Reading zone boundaries from {path}")
    features = read_features(path)
    if looks_projected(features):
        features = reproject_to_wgs84(features)

    merged = {}                                    # location_id -> list of polygons
    for feat in features:
        if feat.get("geometry") is None:
            continue                               # a feature with no shape cannot be drawn
        zone_id = get_location_id(feat["properties"])
        merged.setdefault(zone_id, []).extend(polygons_of(feat["geometry"]))

    result = {}
    for zone_id, polygons in merged.items():
        polygons = _round_coords(polygons)
        lat, lng = centroid_of(polygons)
        geometry = {"type": "MultiPolygon", "coordinates": polygons}
        result[zone_id] = (json.dumps(geometry, separators=(",", ":")),
                           round(lat, 5), round(lng, 5))
    return result