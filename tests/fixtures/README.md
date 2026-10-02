These are real, attributed observations from **Oslo City Bike / Urban Sharing**,
licensed under [NLOD 2.0](https://data.norge.no/nlod/en/2.0). The software's MIT
license does not replace the data license. Retain this attribution and the
manifest when redistributing these fixtures or derived example datasets.

`manifest.json` records source URLs, retrieval times, original source checksums,
fixture checksums, selection rules, and station IDs. The CSVs contain every trip
with **either endpoint** in stations **1023 and 2270**, for the complete UTC months
June and July 2025. There are 1,852 and 1,811 rows respectively. Other stations
appear as counterparties: their demand totals are incomplete. Only the two
selected origin stations have complete departure counts. No rows were deduplicated.
The provider already removes trips below 60 seconds, cancelled trips, and staff moves.

Three GBFS 2.3 snapshots contain every information/status row for those same two
stations at the recorded instants. They are a short demonstration, not seven
days of history. Historical trip coordinates and current station coordinates
can differ; do not assume a station never moves.

Regeneration is a maintainer action: `python3 tools/record_fixtures.py` downloads
full files and records fresh observations. It intentionally changes the fixture
and manifest; review them together. Selection is deterministic for the fetched
source versions, but the station selection can change as source data changes.

Synthetic failures are created only in temporary test directories by the tests
(invalid fields, repeated rows, revised/empty months, and injected exceptions).
They are not represented as provider observations here.
