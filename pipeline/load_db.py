import os
import sqlite3
import pandas as pd

DB = "db/taxi.db"
if os.path.exists(DB):
    os.remove(DB)          # rebuild from scratch each run

conn = sqlite3.connect(DB)
conn.executescript(open("db/schema.sql").read())

# ---- Lookup tables ----
zones = pd.read_csv("data/taxi_zone_lookup.csv")
zones["Borough"] = zones["Borough"].fillna("Unknown")
zones["service_zone"] = zones["service_zone"].fillna("Unknown")

boroughs = pd.DataFrame({"name": sorted(zones["Borough"].unique())})
boroughs["borough_id"] = range(1, len(boroughs) + 1)
boroughs[["borough_id", "name"]].to_sql("borough", conn, if_exists="append", index=False)

z = zones.merge(boroughs, left_on="Borough", right_on="name")
z = z.rename(columns={"LocationID": "location_id", "Zone": "zone_name"})
z[["location_id", "zone_name", "borough_id", "service_zone"]] \
    .to_sql("zone", conn, if_exists="append", index=False)

pd.DataFrame({
    "payment_type_id": [1, 2, 3, 4],
    "label": ["Credit card", "Cash", "No charge", "Dispute"],
}).to_sql("payment_type", conn, if_exists="append", index=False)

pd.DataFrame({
    "rate_code_id": [1, 2, 3, 4, 5, 6],
    "label": ["Standard", "JFK", "Newark", "Nassau/Westchester",
              "Negotiated fare", "Group ride"],
}).to_sql("rate_code", conn, if_exists="append", index=False)

# ---- Trips ----
t = pd.read_parquet("data/clean_trips.parquet").rename(columns={
    "VendorID": "vendor_id",
    "tpep_pickup_datetime": "pickup_dt",
    "tpep_dropoff_datetime": "dropoff_dt",
    "PULocationID": "pu_zone_id",
    "DOLocationID": "do_zone_id",
    "trip_distance": "distance",
    "fare_amount": "fare",
    "tip_amount": "tip",
    "total_amount": "total",
    "payment_type": "payment_type_id",
    "RatecodeID": "rate_code_id",
})
t["pickup_dt"] = t["pickup_dt"].dt.strftime("%Y-%m-%d %H:%M:%S")
t["dropoff_dt"] = t["dropoff_dt"].dt.strftime("%Y-%m-%d %H:%M:%S")

cols = ["vendor_id", "pickup_dt", "dropoff_dt", "pu_zone_id", "do_zone_id",
        "passenger_count", "distance", "fare", "tip", "total",
        "payment_type_id", "rate_code_id", "duration_min", "avg_speed_mph",
        "fare_per_mile", "tip_pct", "pickup_hour", "day_of_week", "is_weekend"]

total = len(t)
for start in range(0, total, 500_000):
    t.iloc[start:start + 500_000][cols].to_sql(
        "trip", conn, if_exists="append", index=False)
    print(f"loaded {min(start + 500_000, total):,} / {total:,}")

# ---- Indexes (after loading, so inserts stay fast) ----
conn.executescript("""
CREATE INDEX idx_trip_pickup_dt ON trip(pickup_dt);
CREATE INDEX idx_trip_pu_zone   ON trip(pu_zone_id);
CREATE INDEX idx_trip_do_zone   ON trip(do_zone_id);
CREATE INDEX idx_trip_hour      ON trip(pickup_hour);
CREATE INDEX idx_trip_payment   ON trip(payment_type_id);
""")
conn.commit()
conn.close()
print("Database built")