CREATE TEMP TABLE clean AS
SELECT * EXCLUDE (_dlt_load_id, _dlt_id, empty_partition)
FROM raw.trips WHERE NOT empty_partition;

CREATE TEMP TABLE stations AS
WITH locations AS (
  SELECT start_station_id AS station_id, start_station_name AS name,
         start_station_latitude AS latitude, start_station_longitude AS longitude,
         started_at AS observed_at FROM clean
  UNION ALL
  SELECT end_station_id, end_station_name, end_station_latitude,
         end_station_longitude, ended_at FROM clean
)
SELECT * FROM locations
QUALIFY row_number() OVER (PARTITION BY station_id ORDER BY observed_at DESC, name) = 1;

CREATE TEMP TABLE daily AS
SELECT start_station_id AS station_id,
       CAST(timezone('Europe/Oslo', started_at) AS DATE) AS service_date,
       count(*) AS departures, avg(duration) AS mean_duration_seconds
FROM clean GROUP BY ALL;

CREATE TEMP TABLE od AS
SELECT start_station_id, end_station_id, count(*) AS trips,
       avg(duration) AS mean_duration_seconds FROM clean GROUP BY ALL;
