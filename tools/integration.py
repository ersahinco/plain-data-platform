"""Destructive only to the disposable sample deployment named in .env."""

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from host import ROOT, compose, settings


def make(*args, **env):
    subprocess.run(["make", *args], cwd=ROOT, env={**os.environ, **env}, check=True)


def graphql(query, variables=None):
    port = settings().get("PDP_UI_PORT", "3000")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.load(response)
    assert not result.get("errors"), result
    return result["data"]


def run_info(run_id):
    return graphql(
        "query($id: ID!) { runOrError(runId:$id) { ... on Run { status startTime endTime } } }",
        {"id": run_id},
    )["runOrError"]


def hashes(storage):
    return {
        str(p.relative_to(storage)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((storage / "data/published").glob("*/data.parquet"))
    }


def main():
    make("run", JOB="trips", MODE="full", SOURCE="sample")
    # Counts, not file bytes: dlt's internal load metadata is intentionally excluded.
    make("run", JOB="trips", MODE="incremental", SOURCE="sample")
    for _ in range(4):
        make("run", JOB="availability", SOURCE="sample")
    make("run", JOB="analysis")
    make("query", DATASET="station_daily")
    make("check")
    storage = Path(settings()["PDP_STORAGE"])
    import duckdb

    with duckdb.connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM read_parquet(?)",
                [str(storage / "data/published/trips/data.parquet")],
            ).fetchone()[0]
            == 3663
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM read_parquet(?)",
                [str(storage / "data/published/availability_history/data.parquet")],
            ).fetchone()[0]
            == 6
        )

    # Exercise the same API used by the UI alongside the documented CLI.
    compose("stop", "daemon")
    cli = None
    try:
        repo = graphql(
            "{ repositoriesOrError { ... on RepositoryConnection { nodes "
            "{ name location { name } } } } }"
        )["repositoriesOrError"]["nodes"][0]
        mutation = """mutation($params: ExecutionParams!) {
          launchRun(executionParams:$params) { __typename
            ... on LaunchRunSuccess { run { runId status } }
            ... on PythonError { message } } }"""
        result = graphql(
            mutation,
            {
                "params": {
                    "selector": {
                        "repositoryLocationName": repo["location"]["name"],
                        "repositoryName": repo["name"],
                        "pipelineName": "trips",
                    },
                    "runConfigData": {},
                }
            },
        )["launchRun"]
        assert result["__typename"] == "LaunchRunSuccess", result
        ui_id = result["run"]["runId"]
        cli = subprocess.Popen(
            ["python3", "tools/host.py", "run"],
            cwd=ROOT,
            env={**os.environ, "JOB": "availability", "SOURCE": "sample"},
            stdout=subprocess.PIPE,
            text=True,
        )
        line = cli.stdout.readline()
        assert "Queued availability:" in line, line
        cli_id = re.search(r"[a-f0-9-]{36}", line).group()
        assert run_info(ui_id)["status"] == run_info(cli_id)["status"] == "QUEUED"
    finally:
        compose("start", "daemon")
    assert cli.wait(timeout=180) == 0
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline and run_info(ui_id)["status"] != "SUCCESS":
        time.sleep(1)
    records = sorted([run_info(ui_id), run_info(cli_id)], key=lambda r: r["startTime"])
    assert all(r["status"] == "SUCCESS" for r in records), records
    assert records[0]["endTime"] <= records[1]["startTime"], records

    compose(
        "run",
        "--rm",
        "--no-deps",
        "reader",
        "python",
        "-c",
        """
from pathlib import Path
assert not Path('/data/ingestion').exists()
assert not Path('/state/storage').exists()
Path('/workspace/permission-check').write_text('ok')
try:
    Path('/dataset/forbidden').write_text('no')
except OSError as exc:
    assert exc.errno in (13, 30)
else:
    raise AssertionError('dataset is writable')
""",
    )
    expected = hashes(storage)
    compose("restart", "code", "web", "daemon")
    compose("up", "-d", "--no-build", "--wait", "--wait-timeout", "180")
    make("run", JOB="availability", SOURCE="sample")
    assert len(hashes(storage)) == len(expected)
    make("backup")
    recovery = Path(tempfile.mkdtemp(prefix="pdp-recovery-"))
    make("restore", SNAPSHOT="latest", RESTORE_TO=str(recovery))
    restored = recovery / "storage"
    assert hashes(restored) == hashes(storage)
    for path in (restored / "dagster").rglob("*.db"):
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    with duckdb.connect(str(restored / "data/ingestion/trips.duckdb"), read_only=True) as conn:
        assert (
            conn.execute("SELECT count(*) FROM raw.trips WHERE NOT empty_partition").fetchone()[0]
            == 3663
        )
    # Exercise recovered dlt state without starting the restored scheduler.
    compose(
        "run",
        "--rm",
        "--no-deps",
        "-v",
        f"{restored}/data:/data",
        "code",
        "python",
        "-c",
        "from pipelines.trips.run import run; run(); "
        "from pipelines.availability.run import run; run()",
    )
    print(f"PASS: queue, CLI/UI serialization, mounts, restart and restored ingestion: {recovery}")


if __name__ == "__main__":
    main()
