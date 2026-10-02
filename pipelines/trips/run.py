from pathlib import Path

from pipelines import common
from pipelines.trips.source import resource


def run(mode="incremental", source="sample"):
    if mode not in ("full", "incremental") or source not in ("sample", "files"):
        raise ValueError("trips requires MODE=full|incremental SOURCE=sample|files")
    directory = (
        common.fixtures() / "trips" if source == "sample" else common.data_root() / "incoming"
    )
    paths = sorted(directory.glob("*.csv"))
    if not paths:
        raise ValueError(f"No monthly files in {directory}")
    pipeline = common.ingestion("trips")
    for path in paths:
        pipeline.run(resource(path, mode, source))
    # Always transform persisted raw data, including after a prior publication failure.
    with common.connect(common.database("trips")) as conn:
        conn.execute(Path(__file__).with_name("transform.sql").read_text())
        common.publish(conn, "clean", "trips", "SELECT count(*) FROM clean WHERE duration < 0")
        common.publish(
            conn,
            "stations",
            "stations",
            "SELECT count(*) - count(DISTINCT station_id) FROM stations",
        )
        common.publish(
            conn, "daily", "station_daily", "SELECT count(*) FROM daily WHERE departures <= 0"
        )
        common.publish(conn, "od", "origin_destination", "SELECT count(*) FROM od WHERE trips <= 0")
