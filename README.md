# NYC Taxi Mobility Dashboard

A full-stack dashboard for exploring NYC yellow taxi trips (January 2019): a cleaning pipeline,
a relational SQLite database, a Flask API and an interactive web dashboard with a zone map.

- **Video walkthrough (5 min):** TODO: paste link here
- **Team:** TODO: team name and members
- **Technical report:** TODO: path or link to the PDF

## Project structure

```
backend/app.py        Flask API (also serves the dashboard)
frontend/             Dashboard (HTML, CSS, JavaScript, Chart.js, Leaflet)
pipeline/             clean.py, load_db.py, build_summary.py, spatial.py, algorithms.py, dump_db.py
db/                   schema.sql, indexes.sql, taxi_dump.sql (database dump)
logs/                 exclusion_summary.csv (what the cleaning step removed and why)
data/                 raw input files (NOT in Git, see "Get the data")
requirements.txt
```

## Requirements

- Python 3.10 or newer (developed on 3.12)
- About 3 GB of free disk space and 8 GB of RAM (the raw file has about 7.7 million rows)
- An internet connection (the dashboard loads Chart.js and Leaflet from a CDN)

## 1. Install

From the project root:

```powershell
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
pip install geopandas            # needed to read the zone boundary shapefile
```

## 2. Get the data

The raw data is too large for GitHub, so it is not in this repository. Create a `data/` folder
in the project root and put these files in it:

| File | Where to get it | Save as |
|---|---|---|
| Yellow taxi trips, January 2019 (Parquet) | https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2019-01.parquet | `data/yellow_tripdata_2019-01.parquet` |
| Taxi zone lookup (CSV) | https://d37ci6vzurychx.cloudfront.net/misc/taxi+_zone_lookup.csv | `data/taxi_zone_lookup.csv` |
| Taxi zone boundaries (shapefile) | https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip | unzip into `data/taxi_zones/` |

All three come from the NYC TLC Trip Record Data page
(https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page).

After unzipping the boundaries, `data/taxi_zones/` must contain `taxi_zones.shp`, `.shx`, `.dbf` and `.prj`.
The final layout is:

```
data/
  yellow_tripdata_2019-01.parquet
  taxi_zone_lookup.csv
  taxi_zones/
    taxi_zones.shp  (+ .shx, .dbf, .prj, .cpg)
```

PowerShell download example:

```powershell
New-Item -ItemType Directory -Force data | Out-Null
Invoke-WebRequest "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2019-01.parquet" -UserAgent "Mozilla/5.0" -OutFile data\yellow_tripdata_2019-01.parquet
Invoke-WebRequest "https://d37ci6vzurychx.cloudfront.net/misc/taxi+_zone_lookup.csv" -UserAgent "Mozilla/5.0" -OutFile data\taxi_zone_lookup.csv
Invoke-WebRequest "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip" -UserAgent "Mozilla/5.0" -OutFile data\taxi_zones.zip
Expand-Archive data\taxi_zones.zip -DestinationPath data -Force
Remove-Item data\taxi_zones.zip
```

If a link no longer works, download the same three files from the TLC page above.

## 3. Build the database

Run these from the project root, in order (the first two take several minutes):

```powershell
python pipeline\clean.py          # cleans trips, writes data/clean_trips.parquet and logs/
python pipeline\load_db.py        # creates db/taxi.db (schema, lookups, zone polygons, trips, indexes)
python pipeline\build_summary.py  # precomputed summary tables for fast unfiltered charts
python pipeline\check_db.py       # sanity check: prints row counts
```

Expected result: about 7.4 million trips and 265 zones, of which 263 have map polygons.

To skip the pipeline, restore the supplied sample dump instead (about 20,000 trips, enough to
try the dashboard):

```
sqlite3 db/taxi.db < db/taxi_dump.sql
```

## 4. Run the app

```powershell
python backend\app.py
```

Open http://127.0.0.1:5000 in a browser. Flask serves both the API and the dashboard, so no
second server is needed. Check the API with http://127.0.0.1:5000/api/health.

## API overview

All endpoints accept the same filters: `start`, `end`, `min_distance`, `max_distance`,
`max_fare`, `zone`, `hour`, `payment`.

| Endpoint | Returns |
|---|---|
| `/api/health` | API and database status |
| `/api/zones`, `/api/zones/geojson` | zone list, zone polygons |
| `/api/stats/summary`, `/by-hour`, `/by-weekday`, `/by-zone` | chart aggregates |
| `/api/top-zones?k=10` | top pickup zones (custom min-heap) |
| `/api/trips?sort=&order=&page=` | sortable, paged trip table |
| `/api/insights/hour-weekend`, `/tip-by-hour`, `/flows`, `/borough` | report insights |

## Data cleaning

`pipeline/clean.py` applies 13 exclusion rules (duplicates, missing fields, impossible
durations, distances, fares, speeds and similar). Every removed row is written to
`logs/excluded_records.csv`, and `logs/exclusion_summary.csv` counts rows per rule.
Derived features: `duration_min`, `avg_speed_mph`, `fare_per_mile`, `tip_pct`,
`pickup_hour`, `day_of_week`, `is_weekend`.

## Custom algorithm

`pipeline/algorithms.py` implements a min-heap and `top_k_zones` by hand (no `heapq`, `Counter`
or `sort_values`). It ranks the busiest pickup zones in O(n log k) time and O(k) space.
