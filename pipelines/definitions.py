from dagster import (
    Definitions,
    Field,
    ScheduleDefinition,
    in_process_executor,
    job,
    op,
)

from pipelines.analysis.run import run as analyze
from pipelines.availability.run import run as load_availability
from pipelines.trips.run import run as load_trips


@op(
    config_schema={
        "mode": Field(str, default_value="incremental"),
        "source": Field(str, default_value="sample"),
    }
)
def ingest_trips(context):
    load_trips(**context.op_config)


@op(config_schema={"source": Field(str, default_value="sample")})
def ingest_availability(context):
    load_availability(**context.op_config)


@op
def analyze_mobility():
    analyze()


@job(executor_def=in_process_executor)
def trips():
    ingest_trips()


@job(executor_def=in_process_executor)
def availability():
    ingest_availability()


@job(executor_def=in_process_executor)
def analysis():
    analyze_mobility()


defs = Definitions(
    jobs=[trips, availability, analysis],
    schedules=[
        ScheduleDefinition(
            name="live_availability",
            job=availability,
            cron_schedule="* * * * *",
            run_config={"ops": {"ingest_availability": {"config": {"source": "live"}}}},
        ),
        ScheduleDefinition(
            name="downloaded_trips",
            job=trips,
            cron_schedule="15 2 * * *",
            execution_timezone="UTC",
            run_config={"ops": {"ingest_trips": {"config": {"source": "files"}}}},
        ),
    ],
)
