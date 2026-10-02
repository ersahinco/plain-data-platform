.DEFAULT_GOAL := help
.PHONY: help bootstrap deploy run query check backup restore snapshots download stop exercise test lint ml
JOB ?= trips
MODE ?= incremental
SOURCE ?= sample
DATASET ?= station_daily
export JOB MODE SOURCE DATASET SNAPSHOT RESTORE_TO MONTH STORAGE EXERCISE
help:
	@echo 'bootstrap deploy run query check backup restore snapshots download stop exercise test lint ml'
bootstrap deploy run query check backup restore snapshots download stop exercise:
	python3 tools/host.py $@
test:
	uv run --frozen --python 3.12 --group dev pytest -q
lint:
	uv run --frozen --python 3.12 --group dev ruff check .
ml:
	uv run --frozen --python 3.12 --group ml python exercises/forecast.py "$(FEATURES)"
