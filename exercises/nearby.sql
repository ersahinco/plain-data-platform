-- Mount nearby_stations. These are straight-line metres, not walking routes.
SELECT * FROM '/dataset/data.parquet'
WHERE station_id IN ('1023', '2270') ORDER BY station_id, straight_line_metres;
