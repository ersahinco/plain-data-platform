import shutil

import pytest

from pipelines import common


@pytest.fixture
def storage(tmp_path, monkeypatch):
    fixture = tmp_path / "fixtures"
    shutil.copytree(common.ROOT / "tests/fixtures", fixture)
    monkeypatch.setenv("PDP_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("PDP_FIXTURES", str(fixture))
    monkeypatch.setenv("DLT_TELEMETRY_ENABLED", "false")
    return tmp_path / "data"


def rows(dataset, columns="*"):
    with common.connect() as conn:
        return conn.execute(
            f"SELECT {columns} FROM read_parquet(?) ORDER BY ALL", [str(common.published(dataset))]
        ).fetchall()
