"""Submit with Dagster's supported CLI; wait using its existing instance API."""

import argparse
import json
import subprocess
import time
import uuid

from dagster import DagsterInstance, DagsterRunStatus


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("job", choices=["trips", "availability", "analysis"])
    parser.add_argument("--mode", default="incremental", choices=["full", "incremental"])
    parser.add_argument("--source", default="sample", choices=["sample", "files", "live"])
    parser.add_argument("--timeout", type=int, default=1900)
    args = parser.parse_args()
    config = {}
    if args.job != "analysis":
        values = {"source": args.source}
        if args.job == "trips":
            values["mode"] = args.mode
        config = {"ops": {f"ingest_{args.job}": {"config": values}}}
    run_id = str(uuid.uuid4())
    subprocess.run(
        [
            "dagster",
            "job",
            "launch",
            "-w",
            "/app/runtime/workspace.yaml",
            "-j",
            args.job,
            "--run-id",
            run_id,
            "--config-json",
            json.dumps(config),
        ],
        check=True,
    )
    print(f"Queued {args.job}: {run_id}", flush=True)
    with DagsterInstance.get() as instance:
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            run = instance.get_run_by_id(run_id)
            if run and run.is_finished:
                print(f"{run_id}: {run.status.value}", flush=True)
                if run.status != DagsterRunStatus.SUCCESS:
                    raise SystemExit(f"Run failed. See Dagster run {run_id} for logs.")
                return
            time.sleep(1)
    raise SystemExit(f"Timed out waiting; run {run_id} may still be active. Inspect the UI.")


if __name__ == "__main__":
    main()
