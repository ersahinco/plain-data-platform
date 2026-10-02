# Dataset contract

Every dataset is a normal Zstandard-compressed Parquet file at
`$PDP_STORAGE/data/published/<dataset>/data.parquet`. Times are UTC timestamps
with time zone unless stated otherwise; identifiers are strings. The source is
[Oslo City Bike / Urban Sharing](https://oslobysykkel.no/en/open-data), NLOD 2.0.
Keep its attribution with derived example outputs. See the fixture manifest for
exact versions, hashes, dates and scope.

| Dataset | Grain and fields |
|---|---|
| `trips` | One source row, including genuine duplicates. `started_at`, `ended_at`, `duration` seconds; `start_station_*` and `end_station_*`: `id`, `name`, `description`, `latitude`, `longitude`; `source_month` as `YYYY-MM`. No invented business ID. |
| `stations` | Latest trip-endpoint location per `station_id`: `name`, WGS84 `latitude`, `longitude`, `observed_at`. Historical coverage, not a guarantee the station is still active. |
| `station_daily` | Origin station and `service_date` in Europe/Oslo: `departures`, `mean_duration_seconds`. Only stations 1023 and 2270 have complete departure totals in the fixture. |
| `origin_destination` | `start_station_id`, `end_station_id`: `trips`, `mean_duration_seconds`. The fixture includes pairs with at least one selected endpoint. |
| `availability_history` | Unique `(source, snapshot_id, station_id)` within the retained window. Fields below. |
| `availability_current` | Latest **observation time**, then feed time and deterministic snapshot ID, per `(source, station_id)`. Adds `evaluated_at`, `age_seconds`, `stale`. |
| `nearby_stations` | Up to three other, non-coincident stations per `station_id`, `alternative_station_id`, `straight_line_metres`. Historical trip coordinates; no route/network claim. |
| `hourly_demand` | Selected origin station and UTC `prediction_at`, complete source-month hourly grid including zeros. `departures` is the target, `previous_hour` and `previous_week` are lagged observed counts; `hour_of_day`, `day_of_week` and `local_time` use Europe/Oslo. `feature_available_at` describes the assumed observation cutoff. |

Availability fields: `source` (`sample` or `live`), `snapshot_id` (SHA-256 of
canonical source payload), `station_id`, `name`, WGS84 `latitude`, `longitude`,
`bikes_available`, `docks_available`, `is_renting`, `is_returning`, `observed_at`
(station's `last_reported`), `feed_at` (feed's `last_updated`), `ingested_at`
(actual fetch/replay time), `ttl_seconds`, `gap_seconds` between distinct station
observation times. `stale` means age exceeds max(300 seconds, twice TTL).
Repeated identical source snapshots upsert the same observations; `ingested_at`
reflects the latest ingestion. `gap_seconds` is null at the window boundary.

Live history retains seven days by observation time, evaluated against ingestion
wall-clock time. Replay retains seven days against the newest recorded feed time
already ingested. A station older than that window disappears from current output;
within the window it remains visible with `stale=true`. Old arrivals cannot replace
newer station status. The service exposes source age at publication time; add
elapsed time since `evaluated_at` when assessing a live dataset later.

The public source is current-state polling, not an event history. Observations
between polls and during outages cannot be recovered. A minute schedule respects
longer advertised TTLs. Station and feed clocks can differ by a few seconds.
GBFS 2.3 is the implemented schema; a major version change fails closed.

Publication validates each candidate before replacing its file on the same local
filesystem. Readers can retain an already-open old inode. Multiple outputs are
**not** an atomic transaction. Ingestion may have committed even when publication
fails; rerun the job to regenerate outputs from raw data. Published output is
fully regenerated, even for incremental ingestion.

## Forecasting assumptions

The exercise is a retrospective one-hour-ahead backtest. Features use starts
strictly before prediction time; no target, future duration or future arrival is
used as a feature. All stations share a chronological 80/20 time split. Model
training uses only the earlier period; early stopping is disabled to avoid a
random validation split. At each evaluation hour, observed demand from earlier
hours can enter the lags. This is not a forecast of the entire horizon at once.

The upstream monthly trip files arrive later than the simulated prediction time.
`feature_available_at` is a pedagogical event-time assumption that hourly demand
is available immediately, not a claim about actual file availability. A live
forecast needs a timely demand source and explicit ingestion-delay handling.
No claim is made that the fitted model beats the seasonal baseline.

## Read-only exploration

Mount only the approved dataset into the reader. Examples:

```sh
make query DATASET=station_daily
make exercise EXERCISE=peak_demand DATASET=station_daily
make exercise EXERCISE=imbalance DATASET=trips
make exercise EXERCISE=nearby DATASET=nearby_stations
make exercise EXERCISE=freshness DATASET=availability_current
make exercise EXERCISE=coverage DATASET=stations
```

For an AI assistant, provide this dictionary, the source attribution, and only
approved Parquet mounts. Ask it to show its SQL, preserve the stated population
scope, and distinguish straight-line distances from travel distances. Never give
it operational DuckDB files, Dagster metadata, source credentials or a Docker
socket. Container mount permissions enforce the boundary regardless of SQL.
