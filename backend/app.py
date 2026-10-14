"""Flask API for the NYC Taxi Mobility Dashboard.

Every endpoint accepts the same filters (see build_filters), so the dashboard can
re-slice every chart with one query string.

Run:  python backend/app.py      ->  http://127.0.0.1:5000
"""
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta

from flask import Flask, jsonify, request
from flask_cors import CORS

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, "..", "pipeline"))
from algorithms import top_k_zones  # our own min-heap, no heapq

DB = os.path.join(HERE, "..", "db", "taxi.db")
FRONTEND = os.path.abspath(os.path.join(HERE, "..", "frontend"))
PAGE_SIZE = 50  # keep in sync with PAGE_SIZE in the frontend

# Flask serves the dashboard too, so one command runs everything.
app = Flask(__name__, static_folder=FRONTEND, static_url_path="")
CORS(app)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
class BadRequest(Exception):
    pass


@app.errorhandler(BadRequest)
def handle_bad_request(err):
    return jsonify({"error": str(err)}), 400


@app.errorhandler(sqlite3.OperationalError)
def handle_db_error(err):
    return jsonify({"error": f"Database error: {err}. Did you run load_db.py?"}), 500


def query(sql, params=()):
    """Run a SELECT and return a list of dicts."""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def as_float(name, value):
    try:
        return float(value)
    except ValueError:
        raise BadRequest(f"'{name}' must be a number")


def as_int(name, value):
    try:
        return int(value)
    except ValueError:
        raise BadRequest(f"'{name}' must be a whole number")


def next_day(date_text):
    """'2019-01-31' -> '2019-02-01', so an end date includes that whole day."""
    try:
        d = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return date_text  # already has a time part, use as given
    return (d + timedelta(days=1)).strftime("%Y-%m-%d")


def build_filters(args):
    """Turn URL parameters into a WHERE clause. Values always go in as ? placeholders."""
    where, params = [], []
    if args.get("start"):
        where.append("pickup_dt >= ?")
        params.append(args["start"])
    if args.get("end"):
        where.append("pickup_dt < ?")
        params.append(next_day(args["end"]))
    if args.get("min_distance"):
        where.append("distance >= ?")
        params.append(as_float("min_distance", args["min_distance"]))
    if args.get("max_distance"):
        where.append("distance <= ?")
        params.append(as_float("max_distance", args["max_distance"]))
    if args.get("max_fare"):
        where.append("fare <= ?")
        params.append(as_float("max_fare", args["max_fare"]))
    if args.get("zone"):
        where.append("pu_zone_id = ?")
        params.append(as_int("zone", args["zone"]))
    if args.get("hour"):
        where.append("pickup_hour = ?")
        params.append(as_int("hour", args["hour"]))
    if args.get("payment"):
        where.append("payment_type_id = ?")
        params.append(as_int("payment", args["payment"]))
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    return clause, params


def and_clause(clause, extra):
    """Add one more condition to a clause that may or may not already have WHERE."""
    return f"{clause} AND {extra}" if clause else f" WHERE {extra}"


def table_or_scan(table, scan_sql, clause, params):
    """No filters -> read the tiny precomputed table. Filters (or missing table) -> scan trip."""
    if not clause:
        try:
            return query(f"SELECT * FROM {table}")
        except sqlite3.OperationalError:
            pass  # summary tables not built yet, fall back to the scan
    return query(scan_sql, params)


# --------------------------------------------------------------------------
# Pages and lookups
# --------------------------------------------------------------------------
@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "trips": query("SELECT COUNT(*) AS n FROM trip")[0]["n"]})


@app.get("/api/zones")
def zones():
    """Zone dropdown: id, name, borough, service zone."""
    return jsonify(query("""
        SELECT z.location_id, z.zone_name, b.name AS borough, z.service_zone
        FROM zone z JOIN borough b ON b.borough_id = z.borough_id
        ORDER BY b.name, z.zone_name"""))


_geojson_cache = None


@app.get("/api/zones/geojson")
def zones_geojson():
    """One GeoJSON feature per zone that has a polygon (cached; it never changes)."""
    global _geojson_cache
    if _geojson_cache is None:
        rows = query("""
            SELECT zb.location_id, zb.geometry, zb.centroid_lat, zb.centroid_lng,
                   z.zone_name, b.name AS borough
            FROM zone_boundary zb
            JOIN zone z ON z.location_id = zb.location_id
            JOIN borough b ON b.borough_id = z.borough_id""")
        _geojson_cache = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": json.loads(r["geometry"]),
                "properties": {
                    "location_id": r["location_id"],
                    "zone_name": r["zone_name"],
                    "borough": r["borough"],
                    "centroid_lat": r["centroid_lat"],
                    "centroid_lng": r["centroid_lng"],
                },
            } for r in rows],
        }
    return jsonify(_geojson_cache)


# --------------------------------------------------------------------------
# Aggregates for the charts
# --------------------------------------------------------------------------
@app.get("/api/stats/summary")
def summary():
    clause, params = build_filters(request.args)
    scan = f"""SELECT COUNT(*) AS trips, ROUND(AVG(fare), 2) AS avg_fare,
                      ROUND(AVG(distance), 2) AS avg_distance,
                      ROUND(AVG(tip_pct), 1) AS avg_tip_pct
               FROM trip{clause}"""
    return jsonify(table_or_scan("summary_overall", scan, clause, params)[0])


@app.get("/api/stats/by-hour")
def by_hour():
    clause, params = build_filters(request.args)
    scan = f"""SELECT pickup_hour AS hour, COUNT(*) AS trips,
                      ROUND(AVG(avg_speed_mph), 1) AS avg_speed
               FROM trip{clause} GROUP BY pickup_hour ORDER BY pickup_hour"""
    return jsonify(table_or_scan("summary_hour", scan, clause, params))


@app.get("/api/stats/by-weekday")
def by_weekday():
    clause, params = build_filters(request.args)
    scan = f"""SELECT day_of_week AS day, COUNT(*) AS trips
               FROM trip{clause} GROUP BY day_of_week ORDER BY day_of_week"""
    return jsonify(table_or_scan("summary_weekday", scan, clause, params))


# Map metrics: the name the frontend sends -> (zone column to group by, SQL expression,
# column that must be non-null to count towards min_trips). Whitelisted, never built from input.
ZONE_METRICS = {
    "pickups":      ("pu_zone_id", "COUNT(*)",                "1"),
    "dropoffs":     ("do_zone_id", "COUNT(*)",                "1"),
    "avg_fare":     ("pu_zone_id", "ROUND(AVG(fare), 2)",     "fare"),
    "avg_distance": ("pu_zone_id", "ROUND(AVG(distance), 2)", "distance"),
    "avg_tip_pct":  ("pu_zone_id", "ROUND(AVG(tip_pct), 1)",  "tip_pct"),
}


@app.get("/api/stats/by-zone")
def by_zone():
    """Per-zone value for the choropleth: {"zones": [{zone_id, value, trips}]}.
    Zones with fewer than min_trips usable trips get value=null (shown grey on the map)."""
    metric = request.args.get("metric", "pickups")
    if metric not in ZONE_METRICS:
        raise BadRequest(f"metric must be one of {sorted(ZONE_METRICS)}")
    min_trips = as_int("min_trips", request.args.get("min_trips", "1"))

    zone_col, expr, usable = ZONE_METRICS[metric]
    clause, params = build_filters(request.args)
    rows = query(f"""SELECT {zone_col} AS zone_id, {expr} AS value, COUNT(*) AS trips,
                            COUNT({usable}) AS usable
                     FROM trip{clause} GROUP BY {zone_col}""", params)
    out = [{"zone_id": r["zone_id"],
            "value": r["value"] if r["usable"] >= min_trips else None,
            "trips": r["trips"]} for r in rows]
    return jsonify({"metric": metric, "zones": out})


@app.get("/api/top-zones")
def top_zones():
    """Top-k pickup zones, ranked by our own min-heap (pipeline/algorithms.py)."""
    k = as_int("k", request.args.get("k", "10"))
    if not 1 <= k <= 100:
        raise BadRequest("k must be between 1 and 100")
    clause, params = build_filters(request.args)
    counts = query(f"SELECT pu_zone_id AS zone_id, COUNT(*) AS trips FROM trip{clause} "
                   "GROUP BY pu_zone_id", params)

    ranked = top_k_zones([(r["zone_id"], r["trips"]) for r in counts], k)  # [(count, zone_id)]
    names = {z["location_id"]: z for z in query(
        "SELECT z.location_id, z.zone_name, b.name AS borough FROM zone z "
        "JOIN borough b ON b.borough_id = z.borough_id")}
    return jsonify([{
        "zone_id": zid,
        "zone_name": names.get(zid, {}).get("zone_name", f"Zone {zid}"),
        "borough": names.get(zid, {}).get("borough", "Unknown"),
        "trips": count,
    } for count, zid in ranked])


# --------------------------------------------------------------------------
# Trip table (sorting + paging)
# --------------------------------------------------------------------------
SORT_COLUMNS = {"pickup_dt", "distance", "fare", "tip", "duration_min",
                "avg_speed_mph", "fare_per_mile", "tip_pct"}


@app.get("/api/trips")
def trips():
    sort = request.args.get("sort", "pickup_dt")
    if sort not in SORT_COLUMNS:
        raise BadRequest(f"sort must be one of {sorted(SORT_COLUMNS)}")
    order = "ASC" if request.args.get("order", "desc").lower() == "asc" else "DESC"
    page = max(1, as_int("page", request.args.get("page", "1")))

    clause, params = build_filters(request.args)
    # trip_id as tie-breaker keeps pages stable when many rows share the same sort value
    sql = f"""SELECT trip_id, pickup_dt, dropoff_dt, pu_zone_id, do_zone_id, passenger_count,
                     distance, fare, tip, total, payment_type_id, duration_min,
                     avg_speed_mph, fare_per_mile, tip_pct
              FROM trip{clause}
              ORDER BY {sort} {order}, trip_id
              LIMIT ? OFFSET ?"""
    return jsonify(query(sql, params + [PAGE_SIZE, (page - 1) * PAGE_SIZE]))


# --------------------------------------------------------------------------
# Insight endpoints (used for the three report insights)
# --------------------------------------------------------------------------
@app.get("/api/insights/hour-weekend")
def hour_weekend():
    """Do weekends have a different daily rhythm? Trips, speed, fare per hour, split by is_weekend."""
    clause, params = build_filters(request.args)
    return jsonify(query(f"""SELECT is_weekend, pickup_hour AS hour, COUNT(*) AS trips,
                                    ROUND(AVG(avg_speed_mph), 1) AS avg_speed,
                                    ROUND(AVG(fare), 2) AS avg_fare
                             FROM trip{clause}
                             GROUP BY is_weekend, pickup_hour
                             ORDER BY is_weekend, pickup_hour""", params))


@app.get("/api/insights/tip-by-hour")
def tip_by_hour():
    """When do people tip most? Card payments only (cash tips are recorded as 0)."""
    clause, params = build_filters(request.args)
    clause = and_clause(clause, "payment_type_id = 1 AND tip_pct IS NOT NULL")
    return jsonify(query(f"""SELECT pickup_hour AS hour, COUNT(*) AS trips,
                                    ROUND(AVG(tip_pct), 2) AS avg_tip_pct
                             FROM trip{clause}
                             GROUP BY pickup_hour ORDER BY pickup_hour""", params))


@app.get("/api/insights/flows")
def flows():
    """Busiest origin -> destination zone pairs (default 10, max 50)."""
    limit = min(max(1, as_int("limit", request.args.get("limit", "10"))), 50)
    clause, params = build_filters(request.args)
    return jsonify(query(f"""
        SELECT t.pu_zone_id, pz.zone_name AS pickup_zone,
               t.do_zone_id, dz.zone_name AS dropoff_zone,
               COUNT(*) AS trips, ROUND(AVG(t.fare), 2) AS avg_fare,
               ROUND(AVG(t.distance), 2) AS avg_distance
        FROM (SELECT * FROM trip{clause}) t
        JOIN zone pz ON pz.location_id = t.pu_zone_id
        JOIN zone dz ON dz.location_id = t.do_zone_id
        GROUP BY t.pu_zone_id, t.do_zone_id
        ORDER BY trips DESC LIMIT ?""", params + [limit]))


@app.get("/api/insights/borough")
def borough():
    """Pickups, average fare, distance and tip per pickup borough."""
    clause, params = build_filters(request.args)
    return jsonify(query(f"""
        SELECT b.name AS borough, COUNT(*) AS trips,
               ROUND(AVG(t.fare), 2) AS avg_fare,
               ROUND(AVG(t.distance), 2) AS avg_distance,
               ROUND(AVG(t.tip_pct), 1) AS avg_tip_pct
        FROM (SELECT * FROM trip{clause}) t
        JOIN zone z ON z.location_id = t.pu_zone_id
        JOIN borough b ON b.borough_id = z.borough_id
        GROUP BY b.name ORDER BY trips DESC""", params))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)