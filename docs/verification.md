# Verification status

Local verification on **2026-10-02** used macOS arm64, Docker Desktop's Linux
arm64 engine, Python 3.12.12, and the pinned repository dependencies.

Implemented and exercised:

- 19 automated pipeline tests: month replacement/convergence, real duplicate
  preservation, empty revisions, ingestion-before-publication recovery, malformed
  input rejection, source-mode isolation, replay recovery, duplicate/delayed
  snapshots, TTL skipping, staleness/retention, fixture hashes, spatial units and
  past-only feature joins.
- The documented bootstrap, deploy, run, query and check commands against all
  three containers. Repeated deployment retains data and waits for health.
- CLI and Dagster UI GraphQL submissions queued together while the daemon was
  stopped, then completed with non-overlapping execution intervals.
- Container restart, a writable private reader workspace, a read-only dataset
  mount, and absence of ingestion state in the reader.
- A cold restic backup, integrity check, verified restore to empty storage,
  matching published-file SHA-256 hashes, restored SQLite/DuckDB integrity and
  rerunning ingestion from restored dlt state.
- All five SQL exercises and the local optional forecasting command. On the
  fixture, the chronological split had 2,072 training and 520 evaluation rows;
  previous-week MAE was about 0.833, model MAE about 0.755 departures/hour. These
  small-fixture results are a workflow check, not a production accuracy claim.
- A complete batch/replay/spatial run with container networking disabled.
- An explicit full-month download and one isolated live GBFS fetch, which
  published 267 station observations. No live schedule is enabled by default.
- Ansible collection installation and syntax checks for both playbooks.

Not locally exercised: installation on a fresh Ubuntu VM, actual SSH deployment
to a remote host, configured production GitHub environment, prolonged live polling,
S3/SFTP copies, hostile multi-tenancy or capacity limits. CI supplies Ubuntu
container integration coverage; it does not substitute for a fresh-host installer
acceptance test. There is no production deployment target configured in this repo.

Optional implemented capabilities are explicit full-month downloads/live polling
and the local ML dependency group. Remote restic destinations are documented
extensions of restic, not tested Make targets. PostgreSQL, shared notebooks,
Terraform and continuous streaming are deliberately not implemented.

Repeat local verification with `make lint test` and, on a disposable sample stack,
`uv run --frozen --python 3.12 python tools/integration.py` using the project environment (for DuckDB).
