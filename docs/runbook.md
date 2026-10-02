# Runbook

## Local operation

`make bootstrap STORAGE=/absolute/path` writes ignored `.env` with paths and IDs.
The default is `~/.local/share/plain-data-platform`, outside Git. Repeating
bootstrap retains existing configuration. Paths must remain on a local filesystem.
`make deploy` builds locally, or pulls an image when `PDP_IMAGE` contains an
immutable digest, then waits for healthy services. Repeated deployment retains
persistent data. `make stop` stops containers without deleting their storage.

`make run JOB=trips MODE=full|incremental SOURCE=sample|files` force-loads or
fingerprint-skips complete monthly CSVs. Each month is replaced with dlt's merge
key. Neither mode invents trip IDs or deduplicates identical records. A full run
reloads the configured files; it does not remove months absent from the folder.

`make run JOB=availability SOURCE=sample` replays one snapshot per run, resuming
from dlt state. After the last snapshot, it republishes without adding rows.
`SOURCE=live` explicitly fetches the GBFS provider, with bounded retries/timeouts.
`make run JOB=analysis` requires a successful trips publication first.

`make check` is the sample acceptance check: it executes all three sample jobs
through the queue, checks the daemon, and queries daily demand. Run it in the
sample deployment. It is not a read-only production health probe. Use Compose
health status, Dagster run history and freshness SQL for production checks.

The Makefile uses host Python and Compose only. Development tests use the locked
Python 3.12 uv environment. Run `make lint test`. The optional model exercise is:

```sh
make ml FEATURES=/absolute/storage/data/published/hourly_demand/data.parquet
```

This installs only the separate ML dependency group in your local environment.
It compares a previous-week baseline with HistGradientBoostingRegressor and
prints chronological holdout MAE. The core image has no scikit-learn dependency.
See the dataset dictionary for backtest timing assumptions.

## Backup and restore

```sh
make backup
make snapshots
make restore SNAPSHOT=latest RESTORE_TO=/absolute/empty/recovery
```

The host wrapper serializes maintenance against CLI commands with a filesystem
lock. It stops the webserver (UI submissions) and daemon (queue/schedules), waits
up to 1,900 seconds for active runs, stops code, and takes an encrypted restic
snapshot of storage. A restic integrity check follows. The previous running
services are restarted in a `finally` block if backup fails. Queued runs remain
queued. Do not bypass maintenance by manually starting services or directly
writing to the databases during a snapshot.

Snapshots include raw DuckDB data, persistent dlt state, published datasets,
Dagster SQLite metadata/logs, workspaces and a release manifest containing image
reference and configuration. They exclude the maintenance lock. Source credentials
and the restic password are deliberately stored separately; escrow them securely.
Lost restic passwords cannot be recovered. Back up the Git revision/image as part
of your release process; data backups do not contain the application image.

Restore refuses nonempty targets and active-storage ancestors/descendants. Restic
verifies the restored files. The result lives under `RESTORE_TO/storage`. No
restored services are started, so schedules remain paused operationally even if
the backed-up metadata says a schedule was enabled.

Before resuming:

1. Check `release.json`, restored Parquet counts and SQLite/DuckDB integrity. Use
   the same application image and code revision as the snapshot.
2. Stop the old deployment. Set `.env` storage/workspace paths to the recovery
   tree; verify ownership matches the configured service UID/GID.
3. Start **code and web only**, with
   `docker compose --env-file .env -f runtime/compose.yaml up -d --no-build code web`.
   Do not start the daemon yet. In the UI, stop schedules/sensors and cancel any
   queued runs that should not replay. Review unfinished runs from before backup.
4. Start the daemon, run one job, and validate published results before enabling
   schedules. `make deploy` starts the daemon too, so use it only after this review.

The integration script checks restic restoration, database integrity and a rerun
using restored dlt state. A same-disk backup protects against mistakes, not disk
loss. For durable off-host copies, use restic's existing SFTP/S3 repository and
`copy` command with separately managed credentials; see
[restic repositories](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html).
The shipped Make wrappers exercise local repositories only. Test retrieval and
restore from your chosen remote location before claiming disaster recovery.

## Troubleshooting

| Symptom | Action |
|---|---|
| No job starts | Check daemon health and queue in Dagster. Queue concurrency is one. Both schedules ship stopped. |
| Failed job | Open its Dagster run and compute logs. Fix source/configuration, then rerun the same command; raw ingestion may already be committed. |
| Spatial extension missing | Rebuild the pinned image while online. Runtime calls only `LOAD spatial`; it never installs extensions. For native tests, use the setup command in CONTRIBUTING. |
| Permission denied | Check host directory UID/GID against `.env`; do not solve this with world-writable storage or root containers. |
| UI unavailable remotely | Use the documented SSH tunnel. Binding to localhost is intentional. |
| Empty source / schema error | Confirm `incoming/YYYY-MM.csv` has the documented header and timezone-aware timestamps. A header-only file intentionally empties that month. |
| CLI wait times out | The run may still be active. Inspect its printed run ID before resubmitting. |
| Stale availability | Compare source time and publication time; inspect failed polls. The feed cannot replay missed observations. |
| Disk nearly full | Inspect raw inputs, dlt state/load packages, Dagster logs and restic snapshots. Establish retention and capacity before deleting anything. |
| Interrupted run | Dagster monitoring detects stopped workers. Inspect the status, then rerun; there is no automatic production retry policy. |
| Restore refused | Use a new empty absolute directory, outside active storage. Never restore over live databases. |

Container logs: `docker compose --env-file .env -f runtime/compose.yaml logs --tail 100`.
Dagster uses local compute logs; Compose rotates its own stdout/stderr logs.
DuckDB transformation memory is capped at 768 MB with two threads; the code
container has a 2 GB total limit. Larger inputs may require more resources or
smaller partitions. No fixed throughput or data-size SLA is promised.

## Add a pipeline

Copy the shape of `pipelines/trips`: source configuration/validation, SQL, and a
small `run()` entry point. Register a regular Dagster op/job and, if needed, a
stopped-by-default schedule. Add meaningful rerun and failure tests. Publish only
after validation and give the new dataset one owner. Keep connectors local until
there is actual reuse. Use the existing queue and dlt state rather than building
a second scheduling, retry or checkpoint mechanism.
