import csv
from unittest.mock import patch

import pytest
from dlt.pipeline.exceptions import PipelineStepFailed

from pipelines import common
from pipelines.trips.run import run
from tests.conftest import rows


def edit_month(change):
    path = common.fixtures() / "trips/2025-06.csv"
    with path.open() as f:
        reader = csv.DictReader(f)
        fields, records = reader.fieldnames, list(reader)
    records = change(records)
    with path.open("w") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def test_full_incremental_converge_and_preserve_duplicates(storage):
    edit_month(lambda records: records + [records[0]])
    run("full")
    expected = rows("trips")
    assert len(expected) == 3664
    run("incremental")
    assert rows("trips") == expected
    run("full")
    assert rows("trips") == expected
    edit_month(lambda records: records[1:])
    run("incremental")
    revised = rows("trips")
    assert len(revised) == 3663
    run("full")
    assert rows("trips") == revised


def test_new_month_and_empty_revision(storage):
    july = common.fixtures() / "trips/2025-07.csv"
    saved = july.read_bytes()
    july.unlink()
    run("incremental")
    assert len(rows("trips")) == 1852
    july.write_bytes(saved)
    run("incremental")
    assert len(rows("trips")) == 3663
    edit_month(lambda _: [])
    run("incremental")
    assert len(rows("trips")) == 1811
    run("full")
    assert len(rows("trips")) == 1811


def test_publication_failure_recovery_from_committed_ingestion(storage):
    run("full")
    before = common.published("trips").read_bytes()
    edit_month(lambda records: records + [records[0]])
    with patch("pipelines.common.publish", side_effect=RuntimeError("synthetic disk failure")):
        with pytest.raises(RuntimeError):
            run("incremental")
    assert common.published("trips").read_bytes() == before
    run("incremental")  # Fingerprint already committed; transform must still run.
    assert len(rows("trips")) == 3664


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("start_station_latitude", "nan"),
        ("start_station_longitude", "181"),
        ("started_at", "not-a-time"),
        ("ended_at", "2020-01-01T00:00:00+00:00"),
        ("start_station_id", ""),
    ],
)
def test_invalid_source_preserves_publication(storage, field, value):
    run("full")
    before = common.published("trips").read_bytes()

    def damage(records):
        records[0][field] = value
        return records

    edit_month(damage)
    with pytest.raises(PipelineStepFailed):
        run("incremental")
    assert common.published("trips").read_bytes() == before


def test_changed_schema_is_rejected(storage):
    run("full")
    before = common.published("trips").read_bytes()
    path = common.fixtures() / "trips/2025-06.csv"
    path.write_text(path.read_text().replace("started_at,", "start_time,", 1))
    with pytest.raises(PipelineStepFailed):
        run("incremental")
    assert common.published("trips").read_bytes() == before


def test_sample_cannot_replace_full_source(storage):
    import shutil

    run("full")
    incoming = storage / "incoming"
    shutil.copytree(common.fixtures() / "trips", incoming)
    before = rows("trips")
    with pytest.raises(PipelineStepFailed):
        run("full", "files")
    assert rows("trips") == before
