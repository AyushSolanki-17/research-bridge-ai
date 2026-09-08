# Research Bridge AI

Python application under `src/research_bridge/`, organized by business capability with domain/application/infrastructure/interfaces layers. The root project builds one library distribution; FastAPI and Uvicorn are optional `server` dependencies.

## Local development

Install uv, then run:

```sh
uv sync --frozen --extra server
uv run --extra server research-bridge-ai-api
```

Python 3.13 is selected by `.python-version`; uv can install it automatically. Open http://localhost:8000/docs or http://localhost:8000/health. The API currently exposes process health only; research functionality is not implemented.

`RB_HOST` defaults to `127.0.0.1`; `RB_PORT` defaults to `8000`. `.env.example` documents optional settings. To load an env file, pass `uv run --env-file .env --extra server research-bridge-ai-api`; dotenv files are not loaded implicitly. No database or provider credentials are required.

For auto-reload during development:

```sh
uv run --extra server uvicorn research_bridge.bootstrap.api:create_app --factory --reload --port 8000
```

The CLI is independent of the web stack:

```sh
uv run research-bridge --help
uv run research-bridge --version
```

Research commands will be added with their capabilities.

## Checks and packaging

```sh
uv run ruff check .
uv run ruff format --check .
uv run --extra server mypy
uv run --extra server pytest
uv run --extra server python scripts/export_openapi.py --check
uv build
uv run python scripts/check_distribution.py
```

Tests cover API behavior, side-effect-free imports and inward layer dependencies. The artifact check verifies wheel/sdist contents and imports the wheel in a clean environment without FastAPI. Keep only the current version's wheel/sdist in `dist/` when running that check.

Export intentional API changes with `uv run --extra server python scripts/export_openapi.py`. CI checks snapshot drift; compatibility with prior published releases must be added when releases exist. The current `0.1.0` is a local development version, not a published release.

## Container

```sh
docker build -t research-bridge-ai:local .
docker run --rm -p 8000:8000 research-bridge-ai:local
```

The image uses the frozen uv lockfile and runs under an unprivileged user. `/health` reports process availability, not database/provider readiness. GitHub CI checks and builds the image; it does not deploy or publish it.

## Project guide

- [Product context](docs/product.md)
- [Architecture](docs/architecture.md)
- [Agent instructions](AGENTS.md)
- [Contract policy](contracts/README.md)
- [Source layout decision](docs/decisions/0001-capability-modules.md)

## Contribution setup

After cloning, enable Conventional Commit hooks with `python3 scripts/install_hooks.py` (Python 3.10+). See [CONTRIBUTING.md](CONTRIBUTING.md) for commit format, DRY ownership review, and governance checks. CI validates proposed commits and PR titles even when local hooks are bypassed; branch protection is needed to require that check before merge.
