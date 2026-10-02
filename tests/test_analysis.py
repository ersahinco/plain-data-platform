import hashlib
import json

from pipelines import common
from pipelines.analysis.run import run as analyze
from pipelines.trips.run import run as trips
from tests.conftest import rows


def test_fixture_integrity():
    root = common.ROOT / "tests/fixtures"
    manifest = json.loads((root / "manifest.json").read_text())
    for path, expected in manifest["files"].items():
        assert hashlib.sha256((root / path).read_bytes()).hexdigest() == expected


def test_spatial_metres_and_hourly_lags(storage):
    trips("full")
    analyze()
    assert len(rows("nearby_stations")) > 0
    with common.connect() as conn:
        conn.execute("LOAD spatial")
        distance = conn.execute("""SELECT ST_Distance(
            ST_Transform(ST_Point(10.75,59.91),'EPSG:4326','EPSG:32633',always_xy:=true),
            ST_Transform(ST_Point(10.76,59.91),'EPSG:4326','EPSG:32633',always_xy:=true))""").fetchone()[
            0
        ]
        assert 550 < distance < 565
        path = str(common.published("hourly_demand"))
        conn.execute(f"CREATE VIEW f AS SELECT * FROM read_parquet({common.literal(path)})")
        assert conn.execute("SELECT count(*) FROM f").fetchone()[0] == 61 * 24 * 2
        assert (
            conn.execute("""SELECT count(*) FROM f a JOIN f b ON a.station_id=b.station_id
           AND a.prediction_at=b.prediction_at+INTERVAL 1 HOUR
           WHERE a.previous_hour IS DISTINCT FROM b.departures""").fetchone()[0]
            == 0
        )
        assert (
            conn.execute("""SELECT count(*) FROM f a JOIN f b ON a.station_id=b.station_id
           AND a.prediction_at=b.prediction_at+INTERVAL 7 DAY
           WHERE a.previous_week IS DISTINCT FROM b.departures""").fetchone()[0]
            == 0
        )
        assert (
            conn.execute("""SELECT count(*) FROM f WHERE feature_available_at > prediction_at
           OR (prediction_at < '2025-06-08' AND previous_week IS NOT NULL)""").fetchone()[0]
            == 0
        )


def test_candidate_validation_preserves_previous_file(storage):
    with common.connect() as conn:
        conn.execute("CREATE TABLE candidate AS SELECT 1 AS value")
        common.publish(conn, "candidate", "example", "SELECT 0")
        before = common.published("example").read_bytes()
        import pytest

        with pytest.raises(ValueError):
            common.publish(conn, "candidate", "example", "SELECT 1")
        assert common.published("example").read_bytes() == before
