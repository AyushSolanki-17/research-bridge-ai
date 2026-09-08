# Research Bridge AI

Python application under `src/research_bridge/`, organized by business capability with domain/application/infrastructure/interfaces layers. The root project builds one library distribution; FastAPI and Uvicorn are optional `server` dependencies.

## Local development

Install uv, then run:

```sh
uv sync --frozen --extra server
uv run --extra server research-bridge-ai-api
```

Python 3.13 is selected by `.python-version`; uv can install it automatically. Open http://localhost:8000/docs or http://localhost:8000/health. The API currently exposes process health only. DOI and OpenAlex identifier resolution is available through the Python library; graph exploration and research HTTP/CLI commands are not yet implemented.

`RB_HOST` defaults to `127.0.0.1`; `RB_PORT` defaults to `8000`. `.env.example` documents optional settings. To load an env file, pass `uv run --env-file .env --extra server research-bridge-ai-api`; dotenv files are not loaded implicitly. No database or provider credentials are required.

For auto-reload during development:

```sh
uv run --extra server uvicorn research_bridge.api.app:create_app --factory --reload --port 8000
```

The CLI is independent of the web stack:

```sh
uv run research-bridge --help
uv run research-bridge --version
```

Research commands will be added with their capabilities.

## Resolve a paper with the library

The library returns canonical metadata and stable source evidence. This example
uses live OpenAlex access; the normal test suite remains offline. See
[provider configuration and limits](src/research_bridge/ingestion/openalex/README.md).

```python
import asyncio

from research_bridge.ingestion.openalex.infrastructure.openalex_adapter import OpenAlexPaperAdapter
from research_bridge.research.papers.application.resolve_paper import ResolvePaper

result = asyncio.run(ResolvePaper(OpenAlexPaperAdapter()).execute("10.7717/peerj.4375"))
print(result.paper.title)
print(result.evidence.to_dict())
```

## Checks and packaging

```sh
uv run ruff check .
uv run ruff format --check .
uv run --extra server mypy
uv run --extra server pytest
uv run --extra server python scripts/export_openapi.py --check
uv build
```

Tests cover API behavior, side-effect-free imports and inward layer dependencies. `uv build` creates the wheel and source distribution.

Export intentional API changes with `uv run --extra server python scripts/export_openapi.py`. CI checks snapshot drift; compatibility with prior published releases must be added when releases exist. The current `0.1.0` is a local development version, not a published release.

## Container

```sh
docker build -t research-bridge-ai:local .
docker run --rm -p 8000:8000 research-bridge-ai:local
```

The image uses the frozen uv lockfile and runs under an unprivileged user. `/health` reports process availability, not database/provider readiness. GitHub CI checks and builds the image; it does not deploy or publish it.

## Project guide

- [Citation Explorer tasks and acceptance criteria](docs/next-steps.md)
- [Product context](docs/product.md)
- [Architecture](docs/architecture.md)
- [Agent instructions](AGENTS.md)
- [Contract policy](contracts/README.md)
- [Source layout decision](docs/decisions/0001-capability-modules.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for commit conventions, ownership review and verification expectations. No hook installation is required.
