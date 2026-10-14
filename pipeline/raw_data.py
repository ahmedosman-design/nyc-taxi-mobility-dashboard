"""One place that knows how to load the raw TLC yellow taxi file."""
import os
import sys
import pandas as pd

RAW_PARQUET = "data/yellow_tripdata_2019-01.parquet"   # official TLC format (preferred)
RAW_CSV = "data/yellow_tripdata_2019-01.csv"           # fallback if only the CSV copy is present
DATETIME_COLS = ["tpep_pickup_datetime", "tpep_dropoff_datetime"]


def load_raw_trips():
    """Load the raw yellow taxi trips, preferring the official .parquet file."""
    if os.path.exists(RAW_PARQUET):
        df = pd.read_parquet(RAW_PARQUET)
        # Parquet keeps real datetimes already; this just guarantees the dtype
        for col in DATETIME_COLS:
            df[col] = pd.to_datetime(df[col])
        return df
    if os.path.exists(RAW_CSV):
        print(f"WARNING: {RAW_PARQUET} not found, falling back to the CSV copy", file=sys.stderr)
        return pd.read_csv(RAW_CSV, parse_dates=DATETIME_COLS)
    sys.exit(f"Raw trip data not found. Download {RAW_PARQUET} from the TLC Trip Record Data page.")