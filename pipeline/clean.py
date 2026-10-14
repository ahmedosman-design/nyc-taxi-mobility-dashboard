import numpy as np
import pandas as pd
from raw_data import load_raw_trips

zones = pd.read_csv("data/taxi_zone_lookup.csv")
df = load_raw_trips()          # reads the official .parquet file (CSV only as a fallback)
rows_in = len(df)

# Duration and speed are needed by the rules, so compute them first
df["duration_min"] = (
    df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"]
).dt.total_seconds() / 60
df["avg_speed_mph"] = df["trip_distance"] / (df["duration_min"] / 60)

# Every row starts with no problem; the first rule that matches wins
df["reason"] = ""

def flag(mask, reason):
    m = mask & (df["reason"] == "")
    df.loc[m, "reason"] = reason

required = ["tpep_pickup_datetime", "tpep_dropoff_datetime", "PULocationID",
            "DOLocationID", "trip_distance", "fare_amount"]

flag(df.duplicated(), "exact duplicate")
flag(df[required].isna().any(axis=1), "missing required field")
flag(~((df["tpep_pickup_datetime"] >= "2019-01-01") &
       (df["tpep_pickup_datetime"] < "2019-02-01")), "pickup outside January 2019")
flag(df["duration_min"] <= 0, "dropoff not after pickup")
flag(df["duration_min"] > 180, "duration over 3 hours")
flag(df["trip_distance"] <= 0, "distance zero or negative")
flag(df["trip_distance"] > 100, "distance over 100 miles")
flag(df["fare_amount"] <= 0, "fare zero or negative")
flag(df["fare_amount"] > 500, "fare over $500")
flag(~df["passenger_count"].between(1, 6), "passenger count not 1-6")
flag(~df["RatecodeID"].between(1, 6), "invalid rate code")
flag(df["avg_speed_mph"] > 60, "speed over 60 mph")
# Practically stationary for 10+ minutes: almost certainly a meter left running
flag((df["avg_speed_mph"] < 1) & (df["duration_min"] > 10), "speed under 1 mph for 10+ min")
# Fare/distance mismatch: tiny distances inflate fare_per_mile (max was 41,500)
flag(df["fare_amount"] / df["trip_distance"] > 100, "fare per mile over $100")

# Tips far larger than the fare are data-entry errors (max tip_pct was 450,000%)
flag((df["payment_type"] == 1) & (df["tip_amount"] > df["fare_amount"] * 3),
     "tip over 3x fare")

# Very short + very cheap trips cannot be validated (kept distances >= 0.1 mi)
flag(df["trip_distance"] < 0.1, "distance under 0.1 miles")
flag(~df["PULocationID"].isin(zones["LocationID"]), "pickup zone not in lookup")
flag(~df["DOLocationID"].isin(zones["LocationID"]), "dropoff zone not in lookup")

# ---- Transparency: log what was excluded ----
excluded = df[df["reason"] != ""]
excluded.to_csv("logs/excluded_records.csv", index=False)

summary = excluded["reason"].value_counts().rename_axis("reason").reset_index(name="rows")
summary["pct_of_raw"] = (summary["rows"] / rows_in * 100).round(4)
summary.to_csv("logs/exclusion_summary.csv", index=False)
print(summary.to_string(index=False))

# ---- Keep the clean rows and add derived features ----
clean = df[df["reason"] == ""].drop(columns="reason").copy()

clean["fare_per_mile"] = clean["fare_amount"] / clean["trip_distance"]
clean["pickup_hour"] = clean["tpep_pickup_datetime"].dt.hour
clean["day_of_week"] = clean["tpep_pickup_datetime"].dt.dayofweek   # 0 = Monday
clean["is_weekend"] = (clean["day_of_week"] >= 5).astype(int)
# Cash tips are recorded as 0, so tip % only means something for card payments
clean["tip_pct"] = np.where(
    clean["payment_type"] == 1,
    clean["tip_amount"] / clean["fare_amount"] * 100,
    np.nan,
)

for c in ["duration_min", "avg_speed_mph", "fare_per_mile", "tip_pct"]:
    clean[c] = clean[c].round(2)

clean.to_parquet("data/clean_trips.parquet", index=False)

print(f"\nRaw rows:      {rows_in:,}")
print(f"Excluded rows: {len(excluded):,}")
print(f"Clean rows:    {len(clean):,}")