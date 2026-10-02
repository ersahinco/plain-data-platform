-- Mount station_daily. Only 1023 and 2270 have complete origins in the fixture.
SELECT station_id, service_date, departures
FROM '/dataset/data.parquet'
WHERE station_id IN ('1023', '2270')
ORDER BY departures DESC LIMIT 10;
