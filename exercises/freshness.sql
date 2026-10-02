-- Mount availability_current. Replay age is evaluated at recorded source time.
SELECT source, station_id, observed_at, evaluated_at, age_seconds, gap_seconds,
       stale, bikes_available=0 AS empty, docks_available=0 AS full
FROM '/dataset/data.parquet' ORDER BY station_id;
