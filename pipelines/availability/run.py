from datetime import UTC, datetime

from pipelines import common
from pipelines.availability.source import resource


def run(source="sample", *, now=None, payload=None):
    if source not in ("sample", "live"):
        raise ValueError("availability requires SOURCE=sample|live")
    now = now or datetime.now(UTC)
    pipeline = common.ingestion("availability")
    pipeline.run(resource(source, now, payload))
    with common.connect(common.database("availability")) as conn:
        # Replay time follows source observations, never the wall clock.
        conn.execute(
            """DELETE FROM raw.observations
          WHERE (source = 'live' AND observed_at < ?::TIMESTAMPTZ - INTERVAL 7 DAY)
             OR (source = 'sample' AND observed_at <
                 (SELECT max(feed_at) FROM raw.observations WHERE source='sample') - INTERVAL 7 DAY)
        """,
            [now],
        )
        conn.execute("""CREATE TEMP TABLE history AS
          WITH distinct_times AS (
            SELECT source, station_id, observed_at,
                   epoch(observed_at - lag(observed_at) OVER (
                     PARTITION BY source, station_id ORDER BY observed_at)) AS gap_seconds
            FROM (SELECT DISTINCT source, station_id, observed_at FROM raw.observations)
          )
          SELECT o.* EXCLUDE (_dlt_id, _dlt_load_id), t.gap_seconds
          FROM raw.observations o JOIN distinct_times t USING (source, station_id, observed_at)
        """)
        conn.execute(
            """CREATE TEMP TABLE current_status AS
          WITH latest AS (
            SELECT * FROM history QUALIFY row_number() OVER (
              PARTITION BY source, station_id
              ORDER BY observed_at DESC, feed_at DESC, snapshot_id DESC) = 1
          ), reference AS (SELECT max(feed_at) AS replay_at FROM history WHERE source='sample')
          SELECT latest.*, CASE WHEN source='sample' THEN replay_at ELSE ? END AS evaluated_at,
                 greatest(0, epoch(evaluated_at - observed_at)) AS age_seconds,
                 age_seconds > greatest(300, ttl_seconds * 2) AS stale
          FROM latest CROSS JOIN reference
        """,
            [now],
        )
        common.publish(
            conn,
            "history",
            "availability_history",
            "SELECT count(*) FROM history WHERE bikes_available < 0 OR docks_available < 0",
        )
        common.publish(
            conn,
            "current_status",
            "availability_current",
            "SELECT count(*) - count(DISTINCT (source, station_id)) FROM current_status",
        )
