"""Explicit download of one full upstream month. Never used by the offline demo."""

import os
import re
import sys

from pipelines import common
from pipelines.availability.source import HTTP

month = sys.argv[1]
if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
    raise SystemExit("Use MONTH=YYYY-MM")
url = f"https://data.urbansharing.com/oslobysykkel.no/trips/v1/{month[:4]}/{month[5:]}.csv"
directory = common.data_root() / "incoming"
directory.mkdir(parents=True, exist_ok=True)
tmp = directory / f".{month}.csv.tmp"
try:
    with HTTP.get(url, stream=True) as response, tmp.open("wb") as f:
        response.raise_for_status()
        for chunk in response.iter_content(1024 * 1024):
            f.write(chunk)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, directory / f"{month}.csv")
finally:
    tmp.unlink(missing_ok=True)
print(f"Downloaded {url}; run trips with SOURCE=files.")
