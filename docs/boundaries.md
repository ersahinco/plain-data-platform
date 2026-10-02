# Supported boundaries

Production target: one Ubuntu 24.04 LTS host with SSH, root/sudo for installation,
local persistent disk, Docker Engine and Compose. Container development is also
exercised on macOS Docker Desktop. Start around two CPU cores and 4 GB RAM, with
enough disk for raw data, DuckDB spill, publications and a backup; measure your
actual inputs. This is a starting allocation, not a throughput guarantee.

Three services use one image: web, daemon, and code. SQLite stores Dagster state;
DefaultRunLauncher starts a process in the code container. QueuedRunCoordinator
admits one run. CPU, memory, PID and log-rotation limits are in Compose. There is
no Docker socket, Postgres, Redis, Kubernetes, broker or second scheduler.

The single code service is one trusted credential domain. The public mobility
example needs no credentials. Add a separate code service when pipelines have
different trust boundaries. Analysts have no host shell or Docker membership;
the localhost UI has operator-level power and is not an analyst portal.

Monthly CSVs are validated and buffered in memory; published Parquet files are
rewritten in full. `full` force-reloads the files configured in the source folder;
it does not erase other months already ingested. An empty file with the correct
header explicitly replaces its month with zero rows. The fixture and downloaded
sources should live in separate deployments: loading sample files into a full
history store would replace those months with the sample.

One active publisher, local POSIX rename, and local disk are required. No HA,
shared NFS database, row-level security, multi-writer DuckDB, cross-file commit,
zero-downtime upgrade, or disaster-recovery SLA is promised. Backup/deployment
pauses submissions and scheduling and waits for active work to finish. There is
no automatic retry of failed Dagster jobs; fix the cause and rerun safely.

Availability history is bounded to seven days. Dagster event history, dlt load
metadata, historical trips and restic snapshots grow; monitor disk and set a
reviewed retention policy. The repository does not silently delete old backups.
Fixture replay is finite. Polling cannot reconstruct missed source changes.

Python packages are exactly pinned with a committed `uv.lock`. Image bases and
GitHub Actions use immutable digests/commits. Docker packages and the Ansible
collection are pinned; Ubuntu base utilities receive normal OS security updates.
The signed spatial extension is tied to the pinned DuckDB release and baked into
the resulting immutable application image. Review and test dependency updates
rather than treating these pins as permanently safe.

Deferred: PostgreSQL for shared SQL/concurrent transactions; JupyterHub with an
existing OIDC provider; Terraform for an actual provider; catalogs; continuous
event transport; model serving. Add one only when a concrete workload needs it.
There is no generic backend abstraction, connector registry or custom orchestrator.
