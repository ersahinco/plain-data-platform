import copy
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
import requests
from dlt.pipeline.exceptions import PipelineStepFailed

from pipelines import common
from pipelines.availability.run import run
from pipelines.availability.source import observations
from tests.conftest import rows


def snapshot(index=0):
    return json.loads((common.fixtures() / f"availability/{index:02}.json").read_text())


def test_replay_resumes_after_publication_failure(storage):
    with patch("pipelines.common.publish", side_effect=RuntimeError("synthetic failure")):
        with pytest.raises(RuntimeError):
            run()
    run()
    assert len(rows("availability_history")) == 4
    run()
    assert len(rows("availability_history")) == 6
    run()
    assert len(rows("availability_history")) == 6


def test_repeated_older_and_delayed_snapshots(storage):
    newer = snapshot(2)
    run(payload=newer)
    expected = rows("availability_current", "station_id, observed_at, bikes_available")
    run(payload=newer)
    assert len(rows("availability_history")) == 2
    run(payload=snapshot(0))
    assert rows("availability_current", "station_id, observed_at, bikes_available") == expected
    assert len(rows("availability_history")) == 4


def test_stale_and_retention(storage):
    value = snapshot()
    now = datetime.fromtimestamp(value["station_status"]["last_updated"], UTC)
    run("live", payload=value, now=now + timedelta(hours=1))
    assert all(row[0] for row in rows("availability_current", "stale"))
    run("live", payload=value, now=now + timedelta(days=8))
    assert rows("availability_history") == []


def test_http_failure_preserves_approved_data_and_cursor(storage):
    run()
    before = common.published("availability_current").read_bytes()
    with patch("pipelines.availability.source.fetch_live", side_effect=requests.Timeout):
        with pytest.raises(PipelineStepFailed):
            run("live")
    assert common.published("availability_current").read_bytes() == before
    run()
    assert len(rows("availability_history")) == 4


def test_live_respects_ttl(storage):
    value = snapshot()
    for feed in value.values():
        feed["ttl"] = 180
    now = datetime.fromtimestamp(value["station_status"]["last_updated"], UTC)
    with patch("pipelines.availability.source.fetch_live", return_value=value) as fetch:
        run("live", now=now)
        run("live", now=now + timedelta(seconds=60))
        assert fetch.call_count == 1
        run("live", now=now + timedelta(seconds=181))
        assert fetch.call_count == 2


def test_invalid_snapshot_is_rejected(storage):
    original = snapshot()
    for feed, field, value in [
        ("station_information", "lat", 100),
        ("station_status", "num_bikes_available", -1),
        ("station_status", "last_reported", "bad"),
    ]:
        damaged = copy.deepcopy(original)
        damaged[feed]["data"]["stations"][0][field] = value
        with pytest.raises((ValueError, TypeError)):
            observations(damaged, "sample", datetime.now(UTC))
