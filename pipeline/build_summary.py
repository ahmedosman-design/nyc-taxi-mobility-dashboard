import sqlite3

conn = sqlite3.connect("db/taxi.db")

conn.executescript("""
DROP TABLE IF EXISTS summary_overall;
DROP TABLE IF EXISTS summary_hour;
DROP TABLE IF EXISTS summary_weekday;
DROP TABLE IF EXISTS summary_zone;

CREATE TABLE summary_overall AS
SELECT COUNT(*) AS trips,
       ROUND(AVG(fare), 2) AS avg_fare,
       ROUND(AVG(distance), 2) AS avg_distance,
       ROUND(AVG(tip_pct), 1) AS avg_tip_pct
FROM trip;

CREATE TABLE summary_hour AS
SELECT pickup_hour AS hour, COUNT(*) AS trips,
       ROUND(AVG(avg_speed_mph), 1) AS avg_speed
FROM trip GROUP BY pickup_hour;

CREATE TABLE summary_weekday AS
SELECT day_of_week AS day, COUNT(*) AS trips
FROM trip GROUP BY day_of_week;

CREATE TABLE summary_zone AS
SELECT pu_zone_id AS zone_id, COUNT(*) AS trips
FROM trip GROUP BY pu_zone_id;
""")
conn.commit()
conn.close()
print("Summary tables built")