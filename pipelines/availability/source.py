import hashlib
import json
import math
import os
from datetime import UTC, datetime

import dlt
from dlt.sources.helpers.requests import Client

from pipelines import common

GBFS = "https://gbfs.urbansharing.com/oslobysykkel.no"
HTTP = Client(
    request_timeout=15, request_max_attempts=3, request_backoff_factor=1, request_max_retry_delay=10
)


def fetch_live():
    headers = {"Client-Identifier": os.environ.get("PDP_CLIENT_IDENTIFIER", "plain-data-platform")}
    payload = {}
    for feed in ("station_information", "station_status"):
        response = HTTP.get(f"{GBFS}/{feed}.json", headers=headers)
        response.raise_for_status()
        payload[feed] = response.json()
    return payload


def observations(payload, source, now):
    info, status = (payload[key] for key in ("station_information", "station_status"))
    for feed in (info, status):
        if feed["version"] != "2.3" or not isinstance(feed["data"]["stations"], list):
            raise ValueError("Expected GBFS 2.3 station feed")
        if not isinstance(feed["ttl"], int) or feed["ttl"] < 0:
            raise ValueError("Invalid feed freshness interval")
    snapshot = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    locations = {str(s["station_id"]): s for s in info["data"]["stations"]}
    if len(locations) != len(info["data"]["stations"]):
        raise ValueError("Duplicate station information")
    rows = []
    seen = set()
    for station in status["data"]["stations"]:
        sid = str(station["station_id"])
        if sid in seen:
            raise ValueError("Duplicate station in snapshot")
        seen.add(sid)
        location = locations[sid]
        lat, lon = float(location["lat"]), float(location["lon"])
        if not (
            math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180
        ):
            raise ValueError("Invalid station coordinates")
        bikes, docks = station["num_bikes_available"], station["num_docks_available"]
        if type(bikes) is not int or type(docks) is not int:
            raise ValueError("Availability counts must be integers")
        if any(type(station[key]) is not bool for key in ("is_renting", "is_returning")):
            raise ValueError("Availability flags must be booleans")
        if min(bikes, docks) < 0:
            raise ValueError("Negative availability")
        reported = datetime.fromtimestamp(station["last_reported"], UTC)
        feed_time = datetime.fromtimestamp(status["last_updated"], UTC)
        # Source clocks may differ by seconds. Bound only implausibly future observations.
        reference = now if source == "live" else feed_time
        if reported.timestamp() > reference.timestamp() + 300:
            raise ValueError("Station observation is implausibly in the future")
        rows.append(
            dict(
                source=source,
                snapshot_id=snapshot,
                station_id=sid,
                name=location["name"],
                latitude=lat,
                longitude=lon,
                bikes_available=bikes,
                docks_available=docks,
                is_renting=bool(station["is_renting"]),
                is_returning=bool(station["is_returning"]),
                observed_at=reported,
                feed_at=feed_time,
                ingested_at=now,
                ttl_seconds=status["ttl"],
            )
        )
    if not rows:
        raise ValueError("Empty station snapshot")
    return rows


def resource(source, now, payload=None):
    @dlt.resource(
        name="observations",
        write_disposition="merge",
        primary_key=["source", "snapshot_id", "station_id"],
    )
    def snapshots():
        state = dlt.current.resource_state()
        if payload is not None:
            value = payload
        elif source == "sample":
            paths = sorted((common.fixtures() / "availability").glob("*.json"))
            index = state.get("next_index", 0)
            if index >= len(paths):
                return
            value = json.loads(paths[index].read_text())
        else:
            if now.timestamp() < state.get("next_live_fetch", 0):
                return
            value = fetch_live()
        rows = observations(value, source, now)
        yield rows
        if payload is None and source == "sample":
            state["next_index"] = index + 1
        if source == "live":
            ttl = max(value[key]["ttl"] for key in ("station_information", "station_status"))
            state["next_live_fetch"] = now.timestamp() + max(60, ttl)

    return snapshots()
