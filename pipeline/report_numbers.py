"""Collect every number the technical report needs from the real database, in one go.

    python pipeline/report_numbers.py

Writes logs/report_numbers.json and prints it. Read-only: it never changes the database.
"""
import csv
import json
import sqlite3
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DB = PROJECT / "db" / "taxi.db"
LOGS = PROJECT / "logs"
OUT = LOGS / "report_numbers.json"


def rows(conn, sql):
    cur = conn.execute(sql)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def main():
    if not DB.exists():
        raise SystemExit(f"Database not found at {DB}. Run the pipeline first.")
    conn = sqlite3.connect(DB)
    result = {}

    # How was this database built? (the maxima reveal which cleaning thresholds were applied)
    result["totals"] = rows(conn, """
        SELECT COUNT(*) AS trips, MIN(pickup_dt) AS first_pickup, MAX(pickup_dt) AS last_pickup,
               ROUND(MAX(duration_min), 1) AS max_duration_min, ROUND(MAX(avg_speed_mph), 1) AS max_speed_mph,
               ROUND(MAX(distance), 1) AS max_distance, ROUND(MAX(fare), 1) AS max_fare,
               ROUND(AVG(fare), 2) AS avg_fare, ROUND(AVG(distance), 2) AS avg_distance,
               ROUND(AVG(tip_pct), 2) AS avg_tip_pct_card
        FROM trip""")[0]
    result["zones"] = rows(conn, "SELECT COUNT(*) AS zones FROM zone")[0]["zones"]
    result["zones_with_polygon"] = rows(conn, "SELECT COUNT(*) AS n FROM zone_boundary")[0]["n"]

    # The exclusion log written by clean.py
    summary = LOGS / "exclusion_summary.csv"
    if summary.exists():
        with open(summary, encoding="utf-8") as f:
            result["exclusion_summary"] = list(csv.DictReader(f))

    result["by_borough"] = rows(conn, """
        SELECT b.name AS borough, COUNT(*) AS trips, ROUND(AVG(t.fare), 2) AS avg_fare,
               ROUND(AVG(t.distance), 2) AS avg_distance
        FROM trip t JOIN zone z ON z.location_id = t.pu_zone_id JOIN borough b ON b.borough_id = z.borough_id
        GROUP BY b.name ORDER BY trips DESC""")

    result["by_hour"] = rows(conn, """
        SELECT pickup_hour AS hour, COUNT(*) AS trips,
               ROUND(SUM(distance) / (SUM(duration_min) / 60.0), 1) AS avg_speed_mph,
               ROUND(AVG(fare), 2) AS avg_fare
        FROM trip GROUP BY pickup_hour ORDER BY pickup_hour""")

    # Weekday vs weekend, per hour. days_* lets the report compare trips PER DAY.
    result["days"] = rows(conn, """
        SELECT is_weekend, COUNT(DISTINCT substr(pickup_dt, 1, 10)) AS days FROM trip GROUP BY is_weekend""")
    result["hour_weekend"] = rows(conn, """
        SELECT is_weekend, pickup_hour AS hour, COUNT(*) AS trips,
               ROUND(SUM(distance) / (SUM(duration_min) / 60.0), 1) AS avg_speed_mph
        FROM trip GROUP BY is_weekend, pickup_hour ORDER BY is_weekend, pickup_hour""")

    # Tipping by hour (card payments only: cash tips are recorded as 0)
    result["tip_by_hour"] = rows(conn, """
        SELECT pickup_hour AS hour, COUNT(*) AS card_trips, ROUND(AVG(tip_pct), 2) AS avg_tip_pct
        FROM trip WHERE payment_type_id = 1 AND tip_pct IS NOT NULL GROUP BY pickup_hour ORDER BY pickup_hour""")

    result["top_flows"] = rows(conn, """
        SELECT pz.zone_name AS pickup_zone, dz.zone_name AS dropoff_zone, COUNT(*) AS trips,
               ROUND(AVG(t.fare), 2) AS avg_fare, ROUND(AVG(t.distance), 2) AS avg_distance
        FROM trip t JOIN zone pz ON pz.location_id = t.pu_zone_id JOIN zone dz ON dz.location_id = t.do_zone_id
        GROUP BY t.pu_zone_id, t.do_zone_id ORDER BY trips DESC LIMIT 10""")

    result["payment_mix"] = rows(conn, """
        SELECT p.label AS payment, COUNT(*) AS trips FROM trip t
        JOIN payment_type p ON p.payment_type_id = t.payment_type_id GROUP BY p.label ORDER BY trips DESC""")
    conn.close()

    LOGS.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))
    print(f"\nSaved to {OUT}")


if __name__ == "__main__":
    main()
