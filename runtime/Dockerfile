FROM ghcr.io/astral-sh/uv:0.11.8@sha256:3b7b60a81d3c57ef471703e5c83fd4aaa33abcd403596fb22ab07db85ae91347 AS uv
FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    DAGSTER_HOME=/state PDP_DATA_ROOT=/data PDP_FIXTURES=/fixtures \
    DLT_TELEMETRY_ENABLED=false HOME=/home/app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project \
    && mkdir -p /home/app/.duckdb /state /data /workspace \
    && python -c "import duckdb; c=duckdb.connect(); c.execute('INSTALL spatial')" \
    && chmod -R a+rX /home/app /app
COPY pipelines /app/pipelines
COPY tools /app/tools
COPY exercises /app/exercises
COPY runtime/dagster.yaml /app/runtime/dagster.yaml
COPY runtime/workspace.yaml /app/runtime/workspace.yaml
USER 10001:10001
