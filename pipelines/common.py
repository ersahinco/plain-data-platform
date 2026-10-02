"""Shared storage and publication primitives; no pipeline framework."""

import json
import os
import uuid
from pathlib import Path

import dlt
import duckdb

ROOT = Path(__file__).resolve().parents[1]


def data_root():
    root = Path(os.environ["PDP_DATA_ROOT"])
    root.mkdir(parents=True, exist_ok=True)
    return root


def fixtures():
    return Path(os.environ.get("PDP_FIXTURES", ROOT / "tests/fixtures"))


def database(name):
    path = data_root() / "ingestion" / f"{name}.duckdb"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def ingestion(name):
    return dlt.pipeline(
        pipeline_name=name,
        pipelines_dir=str(data_root() / "ingestion/dlt"),
        destination=dlt.destinations.duckdb(str(database(name))),
        dataset_name="raw",
        progress=dlt.progress.log(dump_system_stats=False),
    )


def connect(path=":memory:"):
    conn = duckdb.connect(str(path))
    conn.execute("SET TimeZone='UTC'")
    conn.execute("SET threads=2")
    conn.execute("SET memory_limit='768MB'")
    return conn


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def publish(conn, table, dataset, invalid_sql):
    """Check in-memory candidate, write beside target, then replace one file."""
    if conn.execute(invalid_sql).fetchone()[0]:
        raise ValueError(f"{dataset}: quality check failed; previous publication retained")
    directory = data_root() / "published" / dataset
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / f".{uuid.uuid4().hex}.parquet"
    target = directory / "data.parquet"
    try:
        conn.execute(f"COPY {table} TO {literal(candidate)} (FORMAT PARQUET, COMPRESSION ZSTD)")
        os.chmod(candidate, 0o644)
        with candidate.open("rb") as f:
            os.fsync(f.fileno())
        os.replace(candidate, target)
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        candidate.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "event": "published",
                "dataset": dataset,
                "rows": conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0],
            }
        )
    )


def published(dataset):
    return data_root() / "published" / dataset / "data.parquet"
