"""Thin, local-host wrappers around Compose and restic. No remote execution engine."""

import argparse
import fcntl
import json
import os
import secrets
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESTIC_IMAGE = (
    "restic/restic:0.18.1@sha256:39d9072fb5651c80d75c7a811612eb60b4c06b32ffe87c2e9f3c7222e1797e76"
)
DATASETS = (
    "trips",
    "stations",
    "station_daily",
    "origin_destination",
    "availability_current",
    "availability_history",
    "nearby_stations",
    "hourly_demand",
)


def execute(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def settings():
    values = {}
    if (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text().splitlines():
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                values[key] = value
    return {**values, **os.environ}


def compose(*args, capture=False):
    return execute(
        ["docker", "compose", "-f", str(ROOT / "runtime/compose.yaml"), *args],
        env=settings(),
        capture_output=capture,
        text=True,
    )


@contextmanager
def lock(exclusive=True):
    with (Path(settings()["PDP_STORAGE"]) / ".maintenance.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield


def bootstrap():
    env = settings()
    if (ROOT / ".env").exists():
        compose("config", "--quiet")
        print("Existing configuration retained.")
        return
    storage = Path(
        os.environ.get("STORAGE") or Path.home() / ".local/share/plain-data-platform"
    ).resolve()
    if storage == ROOT or ROOT in storage.parents:
        raise SystemExit("Persistent storage must be outside the repository.")
    uid, gid = os.getuid(), os.getgid()
    if uid == 0:
        raise SystemExit(
            "Use Ansible for root-managed deployment; local bootstrap runs as your user."
        )
    storage.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name in ["dagster", "data/ingestion", "data/incoming", "workspaces/operator"]:
        (storage / name).mkdir(mode=0o700, parents=True, exist_ok=True)
    for dataset in DATASETS:
        (storage / "data/published" / dataset).mkdir(mode=0o755, parents=True, exist_ok=True)
    backup = storage.with_name(storage.name + "-backups")
    private = storage.with_name(storage.name + "-secrets")
    backup.mkdir(mode=0o700, exist_ok=True)
    private.mkdir(mode=0o700, exist_ok=True)
    password = private / "restic-password"
    if not password.exists():
        password.write_text(secrets.token_urlsafe(48) + "\n")
        password.chmod(0o600)
    env = {
        "PDP_STORAGE": str(storage),
        "PDP_WORKSPACE": str(storage / "workspaces/operator"),
        "PDP_UID": str(uid),
        "PDP_GID": str(gid),
        "PDP_IMAGE": "plain-data-platform:dev",
        "PDP_BACKUPS": str(backup),
        "PDP_RESTIC_PASSWORD_FILE": str(password),
        "PDP_UI_PORT": "3000",
    }
    (ROOT / ".env").write_text("".join(f"{k}={v}\n" for k, v in env.items()))
    (ROOT / ".env").chmod(0o600)
    compose("config", "--quiet")
    print(f"Prepared {storage}. Keep {password} separately for recovery.")


def restic(*args, restore_to=None):
    env = settings()
    mounts = [
        "-v",
        f"{env['PDP_BACKUPS']}:/repository",
        "-v",
        f"{env['PDP_RESTIC_PASSWORD_FILE']}:/password:ro",
        "-v",
        f"{env['PDP_STORAGE']}:/storage:ro",
    ]
    if restore_to:
        mounts += ["-v", f"{restore_to}:/recovery"]
    execute(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            *mounts,
            "-e",
            "RESTIC_REPOSITORY=/repository",
            "-e",
            "RESTIC_PASSWORD_FILE=/password",
            RESTIC_IMAGE,
            *args,
        ]
    )


@contextmanager
def quiescent():
    previous = compose("ps", "--status", "running", "--services", capture=True).stdout.split()
    services = [s for s in previous if s in ("web", "daemon", "code")]
    try:
        compose("stop", "web", "daemon")
        if "code" in services:
            compose("run", "--rm", "--no-deps", "web", "python", "-m", "tools.idle")
        compose("stop", "code")
        yield
    finally:
        if services:
            compose("start", *services)


def backup():
    env = settings()
    repo = Path(env["PDP_BACKUPS"])
    if not (repo / "config").exists():
        if any(repo.iterdir()):
            raise SystemExit("Backup directory is not an empty restic repository.")
        restic("init")
    with quiescent():
        storage = Path(env["PDP_STORAGE"])
        image_id = execute(
            ["docker", "image", "inspect", env["PDP_IMAGE"], "--format", "{{.Id}}"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        revision = execute(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
        ).stdout.strip()
        (storage / "release.json").write_text(
            json.dumps(
                {
                    "image": env["PDP_IMAGE"],
                    "image_id": image_id,
                    "git_revision": revision,
                    "compose": (ROOT / "runtime/compose.yaml").read_text(),
                    "dagster": (ROOT / "runtime/dagster.yaml").read_text(),
                    "python_lock": (ROOT / "uv.lock").read_text(),
                },
                indent=2,
            )
            + "\n"
        )
        restic("backup", "/storage", "--exclude", "/storage/.maintenance.lock")
        restic("check")


def restore(snapshot, target):
    if not snapshot or not target or not Path(target).is_absolute():
        raise SystemExit("Set SNAPSHOT and an absolute RESTORE_TO directory.")
    path = Path(target).resolve()
    storage = Path(settings()["PDP_STORAGE"]).resolve()
    if path == storage or storage in path.parents or path in storage.parents:
        raise SystemExit("Restore must use separate empty storage.")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(path.iterdir()):
        raise SystemExit("Restore target must be empty.")
    restic("restore", snapshot, "--target", "/recovery", "--verify", restore_to=path)
    print(
        f"Restored to {path}/storage. No services started; review schedules and queued runs first."
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=[
            "bootstrap",
            "deploy",
            "run",
            "query",
            "check",
            "backup",
            "restore",
            "snapshots",
            "download",
            "exercise",
            "stop",
        ],
    )
    args = parser.parse_args()
    if args.command == "bootstrap":
        bootstrap()
        return
    if not (ROOT / ".env").exists():
        raise SystemExit("Run make bootstrap first.")
    with lock(exclusive=args.command != "run"):
        if args.command == "deploy":
            if "@sha256:" in settings()["PDP_IMAGE"]:
                compose("pull", "code")
            else:
                compose("build", "code")
            with quiescent():
                compose(
                    "up", "-d", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "180"
                )
        elif args.command == "run":
            compose(
                "exec",
                "-T",
                "web",
                "python",
                "-m",
                "tools.submit",
                os.environ.get("JOB", "trips"),
                "--mode",
                os.environ.get("MODE", "incremental"),
                "--source",
                os.environ.get("SOURCE", "sample"),
            )
        elif args.command == "query":
            if os.environ.get("DATASET", "station_daily") not in DATASETS:
                raise SystemExit("Unknown dataset")
            compose("run", "--rm", "--no-deps", "reader")
        elif args.command == "exercise":
            exercise = os.environ.get("EXERCISE", "")
            if exercise not in ("peak_demand", "imbalance", "nearby", "freshness", "coverage"):
                raise SystemExit("Unknown exercise")
            if os.environ.get("DATASET", "station_daily") not in DATASETS:
                raise SystemExit("Unknown dataset")
            compose(
                "run",
                "--rm",
                "--no-deps",
                "reader",
                "python",
                "/app/tools/query.py",
                f"/app/exercises/{exercise}.sql",
            )
        elif args.command == "check":
            compose("ps")
            compose("exec", "-T", "daemon", "dagster-daemon", "liveness-check")
            for job in ["trips", "availability", "analysis"]:
                compose("exec", "-T", "web", "python", "-m", "tools.submit", job)
            compose("run", "--rm", "--no-deps", "reader")
        elif args.command == "backup":
            backup()
        elif args.command == "restore":
            restore(os.environ.get("SNAPSHOT"), os.environ.get("RESTORE_TO"))
        elif args.command == "snapshots":
            restic("snapshots")
        elif args.command == "download":
            compose("exec", "-T", "code", "python", "-m", "tools.download", os.environ["MONTH"])
        elif args.command == "stop":
            compose("stop")


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, KeyError) as exc:
        sys.exit(str(exc))
