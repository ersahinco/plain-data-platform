# Contributing

Start with an issue describing a concrete user need. Small fixes, documentation,
new tests and practical examples are welcome. Keep dependencies justified, pinned,
and in the appropriate optional group. Prefer existing dlt and Dagster facilities.

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.12:

```sh
uv python install 3.12
uv sync --frozen --python 3.12 --all-groups
uv run --frozen --python 3.12 python -c "import duckdb; duckdb.connect().execute('INSTALL spatial')"
make lint test
```

That extension installation is a one-time dependency setup. Tests then use local
fixtures. Run `uv run --frozen --python 3.12 python tools/integration.py` against a disposable, deployed sample
stack for Compose/queue/recovery changes. It deliberately runs sample jobs and
restarts services. Do not use your shared production installation.

Add a pipeline folder with its source, SQL, validation and `run()` function, then
register an ordinary Dagster op/job in `pipelines/definitions.py`. Use Dagster's
queue for deployed runs. Do not add a generic connector layer until two real
pipelines require one. Keep one owner for each published dataset.

A PR should explain behavior, the reason for new dependencies, validation, and
limitations. Never commit credentials, private source data, notebook outputs,
or production state. Keep fixtures small, attributed and reproducible; label
synthetic cases. Code is MIT; source data retains its own license.

Maintain a respectful, helpful discussion. Do not publish credentials or private
information in issues; rotate exposed secrets through their issuing service.
