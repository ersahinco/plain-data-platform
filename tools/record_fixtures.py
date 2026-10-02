"""Maintainer tool: record attributed, unmodified source rows (network required)."""

import collections
import csv
import hashlib
import io
import json
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

DEST = Path("tests/fixtures")
BASE = "https://data.urbansharing.com/oslobysykkel.no/trips/v1"
GBFS = "https://gbfs.urbansharing.com/oslobysykkel.no"


def fetch(url):
    req = urllib.request.Request(url, headers={"Client-Identifier": "plain-data-platform-fixtures"})
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read()


def digest(data):
    return hashlib.sha256(data).hexdigest()


months = {}
sources = []
for month in ["2025-06", "2025-07"]:
    url = f"{BASE}/{month[:4]}/{month[5:]}.csv"
    data = fetch(url)
    rows = list(csv.DictReader(io.StringIO(data.decode())))
    months[month] = rows
    sources.append(
        {
            "url": url,
            "sha256": digest(data),
            "retrieved_at": datetime.now(UTC).isoformat(),
            "rows": len(rows),
        }
    )
counts = [collections.Counter(r["start_station_id"] for r in rows) for rows in months.values()]
info = json.loads(fetch(f"{GBFS}/station_information.json"))
active = {str(s["station_id"]) for s in info["data"]["stations"]}
ids = sorted(k for k in active if all(200 <= c[k] <= 900 for c in counts))[:2]
assert len(ids) == 2, "Could not find two small, active stations"
(DEST / "trips").mkdir(parents=True, exist_ok=True)
for month, rows in months.items():
    selected = [r for r in rows if r["start_station_id"] in ids or r["end_station_id"] in ids]
    with (DEST / "trips" / f"{month}.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(selected)
(DEST / "availability").mkdir(exist_ok=True)
for i in range(3):
    payload = {}
    wait = 15
    for feed in ["station_information", "station_status"]:
        url = f"{GBFS}/{feed}.json"
        raw = fetch(url)
        value = json.loads(raw)
        sources.append(
            {"url": url, "sha256": digest(raw), "retrieved_at": datetime.now(UTC).isoformat()}
        )
        value["data"]["stations"] = [
            s for s in value["data"]["stations"] if str(s["station_id"]) in ids
        ]
        assert len(value["data"]["stations"]) == len(ids)
        payload[feed] = value
        wait = max(wait, value.get("ttl", 15))
    (DEST / "availability" / f"{i:02}.json").write_text(json.dumps(payload, indent=2) + "\n")
    if i < 2:
        time.sleep(min(wait + 1, 60))
files = {
    str(p.relative_to(DEST)): digest(p.read_bytes())
    for p in sorted(DEST.rglob("*"))
    if p.is_file() and p.name != "manifest.json"
}
manifest = {
    "provider": "Oslo City Bike / Urban Sharing",
    "license": "NLOD-2.0",
    "license_url": "https://data.norge.no/nlod/en/2.0",
    "station_ids": ids,
    "selection": (
        "All trip rows with either endpoint in station_ids, for complete UTC months "
        "June and July 2025. No trip deduplication. Every recorded station information/status "
        "row for those IDs. Trip demand exercises use only the selected origin stations."
    ),
    "sources": sources,
    "files": files,
}
(DEST / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"station_ids": ids, "files": files}, indent=2))
