import pandas as pd

c = pd.read_parquet("data/clean_trips.parquet")
pd.set_option("display.width", 250)
print(c[["trip_distance", "fare_amount", "duration_min",
         "avg_speed_mph", "fare_per_mile", "tip_pct"]].describe().T.to_string())
print("rows:", len(c))
print("date range:", c["tpep_pickup_datetime"].min(), "to", c["tpep_pickup_datetime"].max())