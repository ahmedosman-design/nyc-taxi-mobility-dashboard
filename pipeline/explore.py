import pandas as pd

df = pd.read_csv(
    "data/yellow_tripdata_2019-01.csv",
    parse_dates=["tpep_pickup_datetime", "tpep_dropoff_datetime"],
)

print(df.shape)                  # rows, columns
print(df.dtypes)                 # type of each column
print(df.isna().sum())           # missing values per column
print(df.duplicated().sum())     # exact duplicate rows
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 250)
print(df.describe().T.to_string())

jan = (df["tpep_pickup_datetime"] >= "2019-01-01") & \
      (df["tpep_pickup_datetime"] < "2019-02-01")
print("--- date check ---")
print("pickups inside January 2019:", jan.sum())
print("pickups OUTSIDE January 2019:", (~jan).sum())
print(df.loc[~jan, "tpep_pickup_datetime"].dt.year.value_counts().sort_index())

dur = (df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"]).dt.total_seconds() / 60
print("--- duration (minutes) ---")
print("max:", dur.max())
print("over 360 min (6 h):", (dur > 360).sum())
print("under or equal 0:", (dur <= 0).sum())

print("--- top 5 fares ---")
print(df["fare_amount"].nlargest(5).to_string())

print("--- congestion_surcharge values (January only) ---")
print(df.loc[jan, "congestion_surcharge"].value_counts(dropna=False).head(5))

print("--- location IDs ---")
print("pickup IDs 264/265:", df["PULocationID"].isin([264, 265]).sum())