-- Indexes for the trip table, created after loading (bulk inserts are much faster without them).
-- Each one backs a dashboard filter or a GROUP BY in the API.
CREATE INDEX idx_trip_pickup_dt ON trip(pickup_dt);          -- date range filter
CREATE INDEX idx_trip_pu_zone   ON trip(pu_zone_id);         -- pickup zone filter, by-zone stats
CREATE INDEX idx_trip_do_zone   ON trip(do_zone_id);         -- dropoff by-zone stats
CREATE INDEX idx_trip_hour      ON trip(pickup_hour);        -- hour filter, by-hour stats
CREATE INDEX idx_trip_payment   ON trip(payment_type_id);    -- payment filter
CREATE INDEX idx_zone_borough   ON zone(borough_id);         -- borough joins