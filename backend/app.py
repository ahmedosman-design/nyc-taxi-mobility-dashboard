import os
import sys
import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS

# Let the backend import your custom algorithm from the pipeline folder
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "pipeline"))
from algorithms import top_k_zones

DB = os.path.join(os.path.dirname(__file__), "..", "db", "taxi.db")

app = Flask(__name__)
CORS(app)


def query(sql, params=()):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows


def build_filters(args):
    """Turn URL parameters into a safe WHERE clause (values go in as ? placeholders)."""
    where, params = [], []
    if args.get("start"):
        where.append("pickup_dt >= ?"); params.append(args["start"])
    if args.get("end"):
        where.append("pickup_dt < ?"); params.append(args["end"])
    if args.get("min_distance"):
        where.append("distance >= ?"); params.append(float(args["min_distance"]))
    if args.get("max_distance"):
        where.append("distance <= ?"); params.append(float(args["max_distance"]))
    if args.get("max_fare"):
        where.append("fare <= ?"); params.append(float(args["max_fare"]))
    if args.get("zone"):
        where.append("pu_zone_id = ?"); params.append(int(args["zone"]))
    if args.get("hour"):
        where.append("pickup_hour = ?"); params.append(int(args["hour"]))
    if args.get("payment"):
        where.append("payment_type_id = ?"); params.append(int(args["payment"]))
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    return clause, params


@app.get("/api/stats/summary")
def summary():
    clause, params = build_filters(request.args)
    sql = f"""SELECT COUNT(*) AS trips,
                     ROUND(AVG(fare), 2) AS avg_fare,
                     ROUND(AVG(distance), 2) AS avg_distance,
                     ROUND(AVG(tip_pct), 1) AS avg_tip_pct
              FROM trip{clause}"""
    return jsonify(query(sql, params)[0])


@app.get("/api/stats/by-hour")
def by_hour():
    clause, params = build_filters(request.args)
    sql = f"""SELECT pickup_hour AS hour, COUNT(*) AS trips,
                     ROUND(AVG(avg_speed_mph), 1) AS avg_speed
              FROM trip{clause}
              GROUP BY pickup_hour ORDER BY pickup_hour"""
    return jsonify(query(sql, params))


@app.get("/api/stats/by-weekday")
def by_weekday():
    clause, params = build_filters(request.args)
    sql = f"""SELECT day_of_week AS day, COUNT(*) AS trips
              FROM trip{clause}
              GROUP BY day_of_week ORDER BY day_of_week"""
    return jsonify(query(sql, params))


@app.get("/api/trips")
def trips():
    clause, params = build_filters(request.args)
    page = max(int(request.args.get("page", 1)), 1)
    # The sort column goes into the SQL text, so it must come from a fixed allowed list
    sort = request.args.get("sort", "pickup_dt")
    if sort not in {"pickup_dt", "distance", "fare", "duration_min"}:
        sort = "pickup_dt"
    direction = "ASC" if request.args.get("order") == "asc" else "DESC"
    sql = f"""SELECT trip_id, pickup_dt, pu_zone_id, distance, fare, tip,
                     duration_min, avg_speed_mph
              FROM trip{clause}
              ORDER BY {sort} {direction} LIMIT 50 OFFSET ?"""
    return jsonify(query(sql, params + [(page - 1) * 50]))


@app.get("/api/zones")
def zones():
    return jsonify(query("""SELECT z.location_id, z.zone_name, b.name AS borough
                            FROM zone z JOIN borough b ON z.borough_id = b.borough_id
                            ORDER BY z.location_id"""))


@app.get("/api/top-zones")
def top_zones():
    k = min(max(int(request.args.get("k", 10)), 1), 265)
    clause, params = build_filters(request.args)
    rows = query(f"SELECT pu_zone_id, COUNT(*) AS c FROM trip{clause} GROUP BY pu_zone_id", params)
    names = {z["location_id"]: z["zone_name"] or "Unknown"
             for z in query("SELECT location_id, zone_name FROM zone")}
    counts = [(r["pu_zone_id"], r["c"]) for r in rows]
    # Your own min-heap does the ranking (no sorted(), no heapq)
    return jsonify([{"zone_id": z, "zone_name": names[z], "trips": c}
                    for c, z in top_k_zones(counts, k)])


if __name__ == "__main__":
    app.run(debug=True, port=5000)