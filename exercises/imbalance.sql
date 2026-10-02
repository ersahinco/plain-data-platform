-- Mount trips. Both arrival and departure counts are complete for these two IDs.
WITH movement AS (
  SELECT start_station_id AS station_id, 1 AS departures, 0 AS arrivals
  FROM '/dataset/data.parquet'
  UNION ALL
  SELECT end_station_id, 0, 1 FROM '/dataset/data.parquet'
)
SELECT station_id, sum(departures) AS departures, sum(arrivals) AS arrivals,
       sum(departures - arrivals) AS net_departures
FROM movement WHERE station_id IN ('1023', '2270') GROUP BY station_id;
