-- EPSG:32633 = UTM zone 33N, metres. always_xy means longitude then latitude.
CREATE TEMP TABLE nearby AS
WITH projected AS (
  SELECT *, ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32633',
                         always_xy := true) AS point FROM stations
)
SELECT a.station_id, b.station_id AS alternative_station_id,
       ST_Distance(a.point, b.point) AS straight_line_metres
FROM projected a CROSS JOIN projected b
WHERE a.station_id <> b.station_id AND ST_Distance(a.point, b.point) > 0
QUALIFY row_number() OVER (PARTITION BY a.station_id ORDER BY straight_line_metres,
                         b.station_id) <= 3;

-- Fill all hours in complete UTC source months, including zero demand hours.
-- Only selected origins have complete histories in the offline fixture.
CREATE TEMP TABLE features AS
WITH months AS (
  SELECT DISTINCT strptime(source_month, '%Y-%m')::TIMESTAMPTZ AS month_start FROM trips
), grid AS (
  SELECT s.station_id, g.hour AS prediction_at
  FROM months m CROSS JOIN selected_stations s,
       generate_series(m.month_start, m.month_start + INTERVAL 1 MONTH - INTERVAL 1 HOUR,
                       INTERVAL 1 HOUR) g(hour)
), demand AS (
  SELECT start_station_id AS station_id, date_trunc('hour', started_at) AS prediction_at,
         count(*) AS departures FROM trips GROUP BY ALL
), hourly AS (
  SELECT grid.*, coalesce(demand.departures, 0) AS departures
  FROM grid LEFT JOIN demand USING (station_id, prediction_at)
)
SELECT h.*, timezone('Europe/Oslo', h.prediction_at)::TIME AS local_time,
       extract(hour FROM timezone('Europe/Oslo', h.prediction_at)) AS hour_of_day,
       extract(isodow FROM timezone('Europe/Oslo', h.prediction_at)) AS day_of_week,
       prev.departures AS previous_hour, week.departures AS previous_week,
       h.prediction_at AS feature_available_at
FROM hourly h
LEFT JOIN hourly prev ON prev.station_id=h.station_id
  AND prev.prediction_at=h.prediction_at - INTERVAL 1 HOUR
LEFT JOIN hourly week ON week.station_id=h.station_id
  AND week.prediction_at=h.prediction_at - INTERVAL 7 DAY;
