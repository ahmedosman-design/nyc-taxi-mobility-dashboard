# NYC Taxi Mobility Dashboard

A full-stack dashboard for exploring NYC yellow taxi trips (January 2019): a cleaning pipeline,
a normalized SQLite database, a Flask API and an interactive dark-themed web dashboard with a zone map.

- **Team:** Junior Nyamu and Ahmed Osman
- **Video walkthrough (5 min):** TODO: paste link here
- **Technical report:** [docs/Technical_Report.pdf](docs/Technical_Report.pdf)

## System architecture

The architecture diagram is at [`docs/taxi_dashboard_architecture.png`](docs/taxi_dashboard_architecture.png).

Data flows left to right through four layers:

1. **Raw data** (not in Git): TLC yellow taxi trips (Parquet), the taxi zone lookup (CSV) and the zone boundaries (shapefile).
2. **Pipeline** (`pipeline/`): `clean.py` removes bad records and logs them, `load_db.py` builds the database,
   `build_summary.py` precomputes chart tables.
3. **Database** (`db/taxi.db`, SQLite): normalized tables `borough`, `zone`, `zone_boundary`, `payment_type`,
   `rate_code` and `trip`, plus indexes for the dashboard's filters.
4. **Backend and frontend**: a Flask API (`backend/app.py`) that also serves the dashboard (`frontend/`),
   so one command starts everything.

## Project structure

```
backend/app.py        Flask API (also serves the dashboard)
frontend/             index.html, app.js, style.css (Chart.js and Leaflet load from a CDN)
pipeline/             clean.py, load_db.py, build_summary.py, spatial.py, algorithms.py,
                      dump_db.py, report_numbers.py
db/                   schema.sql, indexes.sql, taxi_dump.sql (database dump)
docs/                 architecture diagram and the technical report (PDF)
logs/                 exclusion_summary.csv (what the cleaning step removed and why)
data/                 raw input files (mostly NOT in Git, see "Get the data")
requirements.txt
```

## Requirements

- Python 3.10 or newer (developed on 3.12)
- About 3 GB of free disk space and 8 GB of RAM (the raw file has about 7.7 million rows)
- An internet connection (the dashboard loads Chart.js and Leaflet from a CDN)
- A current Chrome or Edge is recommended; other browsers work but show a simpler dropdown menu

## 1. Install

From the project root:

```powershell
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt  # includes geopandas, which reads the zone boundary shapefile
```

## 2. Get the data

The raw data is too large for GitHub, so most of it is not in this repository. Create a `data/` folder
in the project root and put these files in it:

| File | Where to get it | Save as |
|---|---|---|
| Yellow taxi trips, January 2019 (Parquet) | https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2019-01.parquet | `data/yellow_tripdata_2019-01.parquet` |
| Taxi zone lookup (CSV) | https://d37ci6vzurychx.cloudfront.net/misc/taxi+_zone_lookup.csv | `data/taxi_zone_lookup.csv` |
| Taxi zone boundaries (shapefile) | https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip | unzip into `data/taxi_zones/` |

All three come from the NYC TLC Trip Record Data page
(https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page).
The lookup and the shapefile are small and are already committed under `data/`; the Parquet file (110 MB) is not.

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

Expected result: 7,447,044 trips and 265 zones, of which 263 have map polygons.

To skip the pipeline, restore the supplied sample dump instead (about 20,000 trips, enough to try the
dashboard; its numbers will differ from the full dataset). Delete `db/taxi.db` if it exists, then run:

```powershell
python -c "import sqlite3; sqlite3.connect('db/taxi.db').executescript(open('db/taxi_dump.sql', encoding='utf-8').read())"
```

With the `sqlite3` command-line tool installed, `sqlite3 db/taxi.db < db/taxi_dump.sql` does the same.

## 4. Run the app

```powershell
python backend\app.py
```

Open **http://127.0.0.1:5000** in a browser. Flask serves both the API and the dashboard, so no second
server is needed. Check the API with http://127.0.0.1:5000/api/health.

## Dashboard features

- **Filters:** date range, pickup hour, pickup zone, payment type, distance and fare. Apply shows a spinner while data loads.
- **Zone map:** colour zones by pickups, dropoffs, average fare, distance or tip. Hover a zone for a summary card,
  click it for a popup with a button that filters the whole dashboard to that zone. Grey zones have too few trips.
  Zooming is limited to 50% to 150% of the opening view.
- **Charts:** trips and average speed by hour, trips by weekday, and the busiest pickup zones.
  Speed is total miles divided by total hours, so very short trips do not distort it.
- **Trip table:** sortable by any column, 50 rows per page.

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

`pipeline/clean.py` applies 17 ordered exclusion rules (duplicates, missing fields, impossible
durations, distances, fares, speeds, passenger counts, unknown zones and similar). The first rule a row
breaks is its recorded reason, so each removed row is counted once. On the January 2019 file it removes
249,573 of 7,696,617 rows (3.24%), leaving 7,447,044; the largest group is passenger counts outside 1 to 6
(143,693 rows). Every removed row is written to `logs/excluded_records.csv` (generated, not committed),
and `logs/exclusion_summary.csv` counts rows per rule. All thresholds are listed at the top of the cleaning
step and justified in the technical report.

Derived features: `duration_min`, `avg_speed_mph`, `fare_per_mile`, `tip_pct` (card payments only),
`pickup_hour`, `day_of_week`, `is_weekend`.

Note: about 1.7% of trips start and end in zone 264, which the TLC lookup lists with an unknown borough.
They pass every cleaning rule and are kept, but they cannot be placed on the map. The loader names that
zone "Unknown location".

## Custom algorithm

`pipeline/algorithms.py` implements a min-heap and `top_k_zones` by hand (no `heapq`, `Counter`
or `sort_values`). It ranks the busiest pickup zones in O(n log k) time and O(k) space.
Pseudo-code and complexity analysis are in the technical report.

## Design notes

- **SQLite:** one file, no server to install, and fast enough for read-heavy dashboard queries once indexed.
- **Summary tables:** unfiltered charts read tiny precomputed tables. Filtered charts scan the `trip` table,
  which takes a few seconds on the full dataset. That is the trade-off for keeping setup simple.
- **Paging:** the trip table uses `LIMIT/OFFSET`, which slows down on very deep pages. Keyset paging would fix this.

## Troubleshooting

- **Blank page or "API offline":** open http://127.0.0.1:5000 (not `localhost`, and not the HTML file directly)
  and make sure `python backend\app.py` is still running.
- **`FileNotFoundError` in the pipeline:** check the `data/` layout shown above and run the commands from the project root.
- **Shapefile errors:** make sure `pip install -r requirements.txt` finished without errors (it installs geopandas).
- **Port 5000 in use:** close the other program using it, or change the port on the last line of `backend/app.py`.



