CREATE TABLE borough (
    borough_id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE zone (
    location_id INTEGER PRIMARY KEY,
    zone_name TEXT,
    borough_id INTEGER NOT NULL REFERENCES borough(borough_id),
    service_zone TEXT
);

-- One row per zone that has a boundary polygon (zones 264/265 have none).
-- geometry is a GeoJSON MultiPolygon stored as text; the centroid is used for map labels.
CREATE TABLE zone_boundary (
    location_id INTEGER PRIMARY KEY REFERENCES zone(location_id),
    geometry TEXT NOT NULL,
    centroid_lat REAL NOT NULL,
    centroid_lng REAL NOT NULL
);

CREATE TABLE payment_type (
    payment_type_id INTEGER PRIMARY KEY,
    label TEXT NOT NULL
);

CREATE TABLE rate_code (
    rate_code_id INTEGER PRIMARY KEY,
    label TEXT NOT NULL
);

CREATE TABLE trip (
    trip_id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id INTEGER,
    pickup_dt TEXT NOT NULL,
    dropoff_dt TEXT NOT NULL,
    pu_zone_id INTEGER NOT NULL REFERENCES zone(location_id),
    do_zone_id INTEGER NOT NULL REFERENCES zone(location_id),
    passenger_count INTEGER,
    distance REAL,
    fare REAL,
    tip REAL,
    total REAL,
    payment_type_id INTEGER REFERENCES payment_type(payment_type_id),
    rate_code_id INTEGER REFERENCES rate_code(rate_code_id),
    duration_min REAL,
    avg_speed_mph REAL,
    fare_per_mile REAL,
    tip_pct REAL,
    pickup_hour INTEGER,
    day_of_week INTEGER,
    is_weekend INTEGER
);