"""The upstream CSV has no trip ID. A complete month is the replacement key."""

import csv
import hashlib
import io
import math
import re
from datetime import UTC, datetime
from pathlib import Path

import dlt

FIELDS = {"started_at", "ended_at", "duration"} | {
    f"{side}_station_{field}"
    for side in ("start", "end")
    for field in ("id", "name", "description", "latitude", "longitude")
}
COLUMNS = {
    **{name: {"data_type": "text"} for name in sorted(FIELDS)},
    "started_at": {"data_type": "timestamp"},
    "ended_at": {"data_type": "timestamp"},
    "duration": {"data_type": "bigint"},
    **{
        f"{s}_station_{a}": {"data_type": "double"}
        for s in ("start", "end")
        for a in ("latitude", "longitude")
    },
    "source_month": {"data_type": "text"},
    "empty_partition": {"data_type": "bool"},
}


def read_month(path, content):
    month = path.stem
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise ValueError(f"Expected YYYY-MM.csv: {path}")
    rows = []
    with io.StringIO(content.decode("utf-8")) as f:
        reader = csv.DictReader(f)
        if set(reader.fieldnames or ()) != FIELDS:
            raise ValueError(f"{path}: source schema changed")
        for row in reader:
            for key in ("started_at", "ended_at"):
                row[key] = datetime.fromisoformat(row[key].replace("Z", "+00:00"))
                if row[key].utcoffset() is None:
                    raise ValueError("Timestamps must have an explicit timezone")
                row[key] = row[key].astimezone(UTC)
            if row["started_at"].strftime("%Y-%m") != month:
                raise ValueError("Trip belongs to a different source month")
            row["duration"] = int(row["duration"])
            if row["ended_at"] < row["started_at"] or row["duration"] < 0:
                raise ValueError("Invalid trip time or duration")
            for side in ("start", "end"):
                if not row[f"{side}_station_id"]:
                    raise ValueError("Missing station ID")
                for axis, bound in (("latitude", 90), ("longitude", 180)):
                    value = float(row[f"{side}_station_{axis}"])
                    if not math.isfinite(value) or not -bound <= value <= bound:
                        raise ValueError("Invalid station coordinates")
                    row[f"{side}_station_{axis}"] = value
            rows.append({**row, "source_month": month, "empty_partition": False})
    # A sentinel lets dlt replace even a month revised to zero rows.
    return rows or [{"source_month": month, "empty_partition": True}]


def resource(path: Path, mode, source):
    @dlt.resource(
        name="trips", write_disposition="merge", merge_key="source_month", columns=COLUMNS
    )
    def trips():
        state = dlt.current.resource_state()
        if state.get("source_mode", source) != source:
            raise ValueError("Use separate storage for sample and full-file sources")
        state["source_mode"] = source
        fingerprints = state.setdefault("fingerprints", {})
        content = path.read_bytes()
        fingerprint = hashlib.sha256(content).hexdigest()
        if mode == "full" or fingerprints.get(path.stem) != fingerprint:
            yield read_month(path, content)
            fingerprints[path.stem] = fingerprint

    return trips()
