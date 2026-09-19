.DEFAULT_GOAL := help
PYTHON_VERSION ?= 3.13
export UV_PYTHON := $(PYTHON_VERSION)
UV_RUN = uv run --frozen --extra server

.PHONY: help setup check lint format-check types test schema format api smoke dist install-check

help:
	@printf '%s\n' \
	  'make setup         Install frozen development and server dependencies' \
	  'make check         Run lint, formatting, types, offline tests and schema drift' \
	  'make format        Format Python code with Ruff' \
	  'make api           Start the API with development reload' \
	  'make smoke         Exercise the installed API and CLI over local sockets' \
	  'make dist          Build and verify wheel/source archive contents' \
	  'make install-check Verify clean wheel/source installs and consumer typing' \
	  'Override the interpreter with PYTHON_VERSION=3.14'

setup:
	uv sync --frozen --extra server --python $(PYTHON_VERSION)

check: lint format-check types test schema

lint:
	$(UV_RUN) ruff check .

format-check:
	$(UV_RUN) ruff format --check .

types:
	$(UV_RUN) mypy --python-version $(PYTHON_VERSION)

test:
	$(UV_RUN) pytest

schema:
	$(UV_RUN) python scripts/export_openapi.py --check

format:
	$(UV_RUN) ruff format .

api:
	$(UV_RUN) uvicorn research_bridge.api.app:create_app --factory --reload --port 8000

smoke:
	$(UV_RUN) python tests/runtime_smoke.py

dist:
	uv build
	$(UV_RUN) python scripts/verify_distribution.py

install-check: dist
	$(UV_RUN) python scripts/verify_installation.py --python $(PYTHON_VERSION)
