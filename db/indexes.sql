CREATE INDEX idx_trip_fare     ON trip(fare);           -- trip table sort by fare
CREATE INDEX idx_trip_distance ON trip(distance);       -- sort by distance and distance filters
CREATE INDEX idx_trip_duration ON trip(duration_min);   -- sort by duration