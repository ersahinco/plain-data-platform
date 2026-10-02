# Shared deployment

Use one Ubuntu 24.04 LTS host with a local persistent disk, SSH and a sudo-capable
administrator. Allow inbound SSH only; Dagster binds to 127.0.0.1. The image needs
outbound access during installation, and live jobs need their source endpoints.
No cloud-specific service is required. Existing working Docker installations are
retained; the installer never removes an existing Docker package or its data.

On your administrator workstation, install uv, then:

```sh
uv sync --frozen --python 3.12 --group ops
uv run --frozen --python 3.12 --group ops ansible-galaxy collection install -r ops/ansible/requirements.yml
cp ops/ansible/inventory.example.yml ops/ansible/inventory.yml
```

Edit the ignored inventory: SSH host/user, absolute storage paths, a full reviewed
Git SHA and its matching image digest from the image workflow. Confirm the host's
SSH fingerprint through your provider/administrator and put it in `known_hosts`.
Keep SSH host-key verification enabled. Then run:

```sh
uv run --frozen --python 3.12 --group ops ansible-playbook -i ops/ansible/inventory.yml ops/ansible/bootstrap.yml
uv run --frozen --python 3.12 --group ops ansible-playbook -i ops/ansible/inventory.yml ops/ansible/deploy.yml
ssh -L 3000:127.0.0.1:3000 ubuntu@YOUR_HOST
```

Open <http://localhost:3000>. Run operational Make commands on the host, for example
`cd /opt/plain-data-platform && sudo make run JOB=trips MODE=full SOURCE=sample`.
The operator may invoke this over SSH. Ansible handles installation/deployment;
there is no separate remote command runner.

`bootstrap.yml` creates a shell-less UID/GID 10001 for the containers, persistent
storage and a root-only restic password. `deploy.yml` checks out a pinned commit,
writes path-only configuration, pulls the immutable image, pauses submissions,
drains active work and converges Compose. Backup first when upgrading data-writing
code or dependency versions. Keep the old image digest and repository revision.

## Roles and mounts

| Role | Boundary |
|---|---|
| Administrator/operator | SSH/sudo, deployment, backup, access assignment, Dagster UI. Fully trusted. |
| Engineer | Local development; production changes proposed through Git and reviewed deployment. No production credentials by default. |
| Analyst | Approved dataset directories mounted read-only, one private writable workspace; no host shell, Docker socket or Docker group. |
| Pipeline code | Public example needs no secrets. Only the code service receives operational data and source-secret mounts. |

`make query` demonstrates a one-shot reader with no network, one dataset mount,
a private workspace, memory/CPU limits, no capabilities and a read-only root
filesystem. It is an **operator command**: do not give analysts Docker privileges
just to run it. Administrators may run readers under each analyst's numeric UID
with a workspace owned by that UID. Mount the dataset directory, so atomic
replacement is visible, rather than mounting an individual Parquet inode.

The shipped local reader shares the operator UID for convenience. For an actual
analyst, set `PDP_UID`, `PDP_GID` and `PDP_WORKSPACE` to the assigned values when
invoking the reader. Make the personal workspace mode 0700; grant only approved
dataset mounts. Dataset files are 0644 *inside storage*, while parent operational
directories are 0700. Readers cannot walk the host's storage tree.

Production secrets belong in root-managed files outside the checkout. Add an
explicit Compose secret/file mount to **code only**, scoped to that source and
readable by its service UID. Do not put secret values in `.env`, Dagster run
configuration, logs or images. All pipelines in one code service share its trust
boundary; separate code services are required for mutually restricted sources.
Never mount production source credentials or ingestion databases in notebooks.

Shared notebooks are deferred. If introduced, use the existing identity provider
via OIDC, verified group-to-dataset mount assignments, individual workspaces and
resource limits. JupyterHub application roles alone do not enforce dataset access.

## GitHub delivery

PRs run lint, failure/recovery tests, Ansible syntax checks and the offline Compose
integration suite. Successful main-branch runs build a linux/amd64 image in GHCR,
tagged by commit; the workflow summary records its digest. The same source also
builds on arm64 locally. Make the GHCR package public for unauthenticated host
pulls, or configure registry credentials on the host without committing them.

The manual deployment workflow needs a `production` GitHub environment:

- Variables `DEPLOY_HOST` and `DEPLOY_USER`.
- Secrets `DEPLOY_SSH_KEY` and `DEPLOY_KNOWN_HOSTS` (verified complete host-key line).
- Reviewers and allowed deployment branches configured by repository administrators.
- A reviewed commit and matching immutable image digest as inputs.

The workflow does not provision a VM or purchase services. It uses SSH and sudo on
the already configured target. There is no unattended production deployment.

## Live sources

Use a **separate storage root/deployment** from the offline fixture walkthrough.
The sample is a subset of the same months: mixing it with full files would replace
full months with sample rows. The pipeline rejects switching `sample`/`files`
within an initialized ingestion store. Download explicit months on the target:

```sh
make download MONTH=2025-06
make download MONTH=2025-07
make run JOB=trips MODE=full SOURCE=files
make run JOB=trips MODE=incremental SOURCE=files
make run JOB=availability SOURCE=live
```

Re-download a revised month before running incremental ingestion. Downloads use
a temporary file and atomic rename. The `downloaded_trips` schedule loads files
already present in `incoming`; it does not discover/download new months. Set
`PDP_CLIENT_IDENTIFIER` in `.env` to identify your deployment to the GBFS provider.

Schedules ship stopped. Enable `live_availability` explicitly in Dagster for
minute polling, or `downloaded_trips` for daily processing of downloaded files.
The CLI, UI and these schedules submit the same jobs through one queue. Network
failures leave approved datasets unchanged. Inspect failed runs before retrying.
