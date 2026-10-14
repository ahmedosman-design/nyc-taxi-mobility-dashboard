import json
import os
import sys
import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, "..", "pipeline"))
from algorithms import top_k_zones

DB = os.path.join(HERE, "..", "db", "taxi.db")
FRONTEND = os.path.abspath(os.path.join(HERE, "..", "frontend"))

# Flask serves the dashboard files too, so one command runs everything
app = Flask(__name__, static_folder=FRONTEND, static_url_path="")
CORS(app)


@app.get("/")
def index():
    return app.send_static_file("index.html")


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


def table_or_scan(table, scan_sql, clause, params):
    """No filters -> read the tiny precomputed table. Filters -> scan the big table."""
    if not clause:
        return query(f"SELECT * FROM {table}")
    return query(scan_sql, params)


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
    scan = f"""SELECT