-- Mount stations. A 300-metre circle is an exercise, not a routing isochrone.
LOAD spatial;
WITH projected AS (
 SELECT station_id,
        ST_Transform(ST_Point(longitude,latitude),'EPSG:4326','EPSG:32633',
                     always_xy:=true) AS point
 FROM '/dataset/data.parquet'
)
SELECT station_id, ST_Area(ST_Buffer(point,300)) AS catchment_square_metres
FROM projected WHERE station_id IN ('1023','2270');
