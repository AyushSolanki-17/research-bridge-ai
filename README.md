# Research Bridge AI

Python application under `src/research_bridge/`, organized by business capability with domain/application/infrastructure/interfaces layers. The root project builds one library distribution; FastAPI and Uvicorn are optional `server` dependencies.

## Local development

Install uv, then run:

```sh
uv sync --frozen --extra server
uv run --extra server research-bridge-ai-api
```

Python 3.13 is selected by `.python-version`; uv can install it automatically. Open http://localhost:8000/docs or http://localhost:8000/health. DOI/OpenAlex resolution and bounded outgoing citation exploration are available through the Python library, HTTP and CLI. Title search with explicit candidate selection is also available. Incoming citations and filtering are not yet implemented.

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

Resolve a paper or explore its outgoing citations (these commands access OpenAlex):

```sh
uv run research-bridge resolve '10.7717/peerj.4375'
uv run research-bridge explore W2741809807 --depth 2 --max-nodes 50 --max-edges 200 --max-requests 100 --max-seconds 30
```

Results are JSON on stdout. Resolution errors are JSON on stderr. CLI exit codes:
0 success, 2 invalid input/settings, 3 missing seed, 4 provider failure, 5 truncated
exploration, 130 cancellation. Failed or truncated exploration preserves its
available graph on stdout; inspect `status`, `stop_reasons` and `unresolved`.

With the local API running:

```sh
curl -X POST http://localhost:8000/v1/papers/resolve -H 'Content-Type: application/json' -d '{"identifier":"10.7717/peerj.4375"}'
curl -X POST http://localhost:8000/v1/graphs/outgoing -H 'Content-Type: application/json' -d '{"identifier":"W2741809807","limits":{"depth":2,"max_nodes":50}}'
```

Omitted graph limits use library defaults. The research endpoints are read-only
operations expressed as POST requests and require no application authentication.
See [HTTP responses and error codes](src/research_bridge/api/README.md). Network
access is performed only when executing a research command or request.

## Search by title and select a candidate

```sh
uv run research-bridge search 'The state of OA' --page-size 5
# Use next_page with the same query and limits to review another page:
uv run research-bridge search 'The state of OA' --page-size 5 --page 2
curl -X POST http://localhost:8000/v1/papers/search -H 'Content-Type: application/json' -d '{"query":"The state of OA","limits":{"page_size":5}}'
```

Review `candidates` using their titles, authors, dates and venues. Choose the intended
candidate's `paper.identifiers.openalex_id.value`, then pass that identifier to
`research-bridge explore IDENTIFIER` or `POST /v1/graphs/outgoing`. No candidate is
automatically selected. Invalid selections follow existing identifier error behavior.
An empty search is successful and returns no candidates.

```python
import asyncio

from research_bridge.ingestion.openalex.infrastructure.openalex_adapter import OpenAlexPaperAdapter
from research_bridge.research.papers.application import SearchLimits, SearchPapers

candidates = asyncio.run(
    SearchPapers(OpenAlexPaperAdapter()).execute("The state of OA", SearchLimits(page_size=5))
)
for candidate in candidates.candidates:
    print(candidate.paper.identifiers.openalex_id.value, candidate.paper.title)
# After reviewing the output, use your chosen identifier with ExploreOutgoing.
```

Search returns `complete` at provider end, `more` with `next_page`, `truncated`
at an acquisition limit, or `failed` on provider errors. CLI codes are 0 for
complete/more, 5 for truncated and 4 for failed; partial candidates remain on stdout.
Cancellation exits 130 and stops requests. Search limits default to 10 candidates
per page, 100 total unique candidates, 20 physical requests and 30 seconds per call.
Later pages replay prior provider pages for deduplication, consuming the same call
budget. See [pagination and limit semantics](src/research_bridge/research/papers/README.md#title-candidate-search).

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

## Explore outgoing citations with the library

```python
from research_bridge.knowledge_graph.application import ExplorationLimits, ExploreOutgoing

graph = asyncio.run(
    ExploreOutgoing(OpenAlexPaperAdapter()).execute(
        result, ExplorationLimits(depth=2, max_nodes=50)
    )
)
print(graph.status, graph.stop_reasons)
```

This continues the resolution example using its ingested seed. Read the
[traversal, budget and partial-result contract](src/research_bridge/knowledge_graph/README.md)
before interpreting graph completeness.

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
