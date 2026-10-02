import json
from pathlib import Path

from pipelines import common


def run():
    with common.connect() as conn:
        conn.execute("LOAD spatial")  # Installed at build time; never INSTALL at runtime.
        for dataset in ("trips", "stations"):
            path = common.literal(common.published(dataset))
            conn.execute(f"CREATE VIEW {dataset} AS SELECT * FROM read_parquet({path})")
        ids = json.loads((common.fixtures() / "manifest.json").read_text())["station_ids"]
        conn.execute("CREATE TEMP TABLE selected_stations (station_id VARCHAR)")
        conn.executemany("INSERT INTO selected_stations VALUES (?)", [(sid,) for sid in ids])
        conn.execute(Path(__file__).with_name("transform.sql").read_text())
        common.publish(
            conn,
            "nearby",
            "nearby_stations",
            "SELECT count(*) FROM nearby WHERE straight_line_metres <= 0",
        )
        common.publish(
            conn,
            "features",
            "hourly_demand",
            "SELECT count(*) FROM features WHERE feature_available_at > prediction_at",
        )
