"""Wait for active workers to finish after web and daemon have stopped."""

import time

from dagster import DagsterInstance, DagsterRunStatus, RunsFilter

with DagsterInstance.get() as instance:
    for _ in range(1900):
        active = instance.get_runs(
            filters=RunsFilter(
                statuses=[
                    DagsterRunStatus.STARTING,
                    DagsterRunStatus.STARTED,
                    DagsterRunStatus.CANCELING,
                ]
            )
        )
        if not active:
            break
        time.sleep(1)
    else:
        raise SystemExit("Active runs did not drain; aborting maintenance. Inspect Dagster.")
