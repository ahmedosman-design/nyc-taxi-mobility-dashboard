import pandas as pd

df = pd.read_csv(
    "data/yellow_tripdata_2019-01.csv",
    parse_dates=["tpep_pickup_datetime", "tpep_dropoff_datetime"],
)

print(df.shape)                  # rows, columns
print(df.dtypes)                 # type of each column
print(df.isna().sum())           # missing values per column
print(df.duplicated().sum())     # exact duplicate rows
print(df.describe().T)           # min / max / mean per column