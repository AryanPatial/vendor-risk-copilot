VENV := .venv
PY := $(VENV)/bin/python
PG_BIN := /opt/homebrew/opt/postgresql@17/bin

.PHONY: install db migrate api ui test test-all lint fmt eval clean

install:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -U pip
	$(VENV)/bin/pip install -e ".[dev]"

db:
	brew services start postgresql@17
	$(PG_BIN)/createdb qre || true
	$(PG_BIN)/psql -d qre -c "CREATE EXTENSION IF NOT EXISTS vector;"

migrate:
	$(VENV)/bin/qre db migrate

api:
	$(VENV)/bin/uvicorn qre.api.main:app --reload --port 8000

ui:
	$(VENV)/bin/streamlit run ui/app.py

test:
	$(PY) -m pytest tests/unit -q

test-all:
	$(PY) -m pytest -q --run-db

lint:
	$(VENV)/bin/ruff check src tests ui
	$(VENV)/bin/mypy

fmt:
	$(VENV)/bin/ruff check --fix src tests ui
	$(VENV)/bin/ruff format src tests ui

eval:
	$(VENV)/bin/qre eval run -c acme

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache
