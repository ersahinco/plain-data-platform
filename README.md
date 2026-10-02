# Plain Data Platform

**Practical data infrastructure for everyday teams.**

A small, single-host data platform built from Dagster, dlt, DuckDB, Parquet,
Docker Compose, Ansible, and restic. Three long-running containers share one
application image. No cloud account is required.

The included Oslo City Bike example covers monthly batch loads, incremental
month replacement, recorded/live availability micro-batches, spatial SQL,
and an optional demand-forecasting exercise. [Data attribution](tests/fixtures/README.md).

## Try the offline example

Prerequisites: Docker with Compose v2+, Python 3.12+ for host commands, Git and Make.
Allow approximately 4 GB RAM for the stack. The first image build and restic image
pull need internet; jobs use the included fixtures without network access.

```sh
git clone https://github.com/ersahinco/plain-data-platform.git
cd plain-data-platform
make bootstrap                     # Storage defaults outside the checkout
make deploy                        # Build the locked image; start three services
make run JOB=trips MODE=full SOURCE=sample
make run JOB=trips MODE=incremental SOURCE=sample
make run JOB=availability SOURCE=sample
make run JOB=analysis
make query DATASET=station_daily
make check
make backup
make snapshots
make restore SNAPSHOT=latest RESTORE_TO=/tmp/plain-data-recovery
```

Open <http://localhost:3000> for Dagster. The second trips run keeps the same
3,663 source rows. Each availability run consumes the next saved snapshot;
rerunning after the third snapshot is safe. `make check` runs the three sample
jobs and queries a result. It writes sample outputs: use a separate deployment
for the walkthrough and for real sources.

Restore verifies files into `/tmp/plain-data-recovery/storage` and starts no
services. See the [recovery procedure](docs/runbook.md#backup-and-restore) before
using recovered state. Keep the generated restic password separately from the
backup. A backup on the same disk is only a local recovery exercise.

## What is deliberately small

- One Ubuntu 24.04 host, local persistent storage, one queued run at a time.
- dlt owns ingestion state; DuckDB owns SQL; Dagster owns queueing, schedules and logs.
- Parquet publication is validated and atomic **per file**, with full small-output rewrites.
- Live availability is polling, not an event log; missed changes cannot be recovered.
- Trusted operators use the UI through SSH. Analysts receive only approved read-only
  dataset mounts and their own writable workspace.

PostgreSQL, shared notebooks, Terraform, continuous streaming, catalogs, and
model-serving services are deferred. See [boundaries](docs/boundaries.md) and
[verification status](docs/verification.md) for what was actually exercised.

## Find your way

| Path | Purpose |
|---|---|
| `pipelines/` | Standard Dagster definitions; pipeline-local sources, SQL and entry points |
| `runtime/` | Pinned image, three-service Compose configuration, Dagster instance |
| `ops/ansible/` | Ubuntu installation and immutable-image deployment |
| `tools/` | Thin command, backup, query and verification helpers |
| `tests/` | Real offline fixtures and failure/recovery tests |
| `exercises/` | Business SQL and optional scikit-learn forecast |
| `docs/` | [Runbook](docs/runbook.md), [datasets](docs/datasets.md), [shared deployment](docs/deployment.md) |

[Contributing](CONTRIBUTING.md) · [MIT license](LICENSE) ·
[Original public data](https://oslobysykkel.no/en/open-data)
