# Research Bridge AI

Python application under `src/research_bridge/`, organized by business capability with domain/application/infrastructure/interfaces layers. The root project builds one library distribution; FastAPI and Uvicorn are optional `server` dependencies.

## Local development

Install uv, then run:

```sh
uv sync --frozen --extra server
uv run --extra server research-bridge-ai-api
```

Python 3.13 is selected by `.python-version`; uv can install it automatically. Open http://localhost:8000/docs or http://localhost:8000/health. DOI/OpenAlex resolution and bounded outgoing, incoming and combined citation exploration are available through the Python library, HTTP and CLI. Title search with explicit candidate selection is also available. Metadata filters and source inspection are available on graph results.

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
A valid query with no matches succeeds with no candidates. Blank queries are rejected.

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

## Explore incoming or combined citations

```sh
uv run research-bridge explore W2741809807 --mode incoming --depth 2
uv run research-bridge explore W2741809807 --mode both --depth 3 --max-requests 100
curl -X POST http://localhost:8000/v1/graphs/explore -H 'Content-Type: application/json' -d '{"identifier":"W2741809807","mode":"both","limits":{"depth":2}}'
```

```python
from research_bridge.knowledge_graph.application import ExploreCitations, ExplorationLimits

graph = asyncio.run(
    ExploreCitations(OpenAlexPaperAdapter()).execute(
        "W2741809807", ExplorationLimits(depth=2), mode="both"
    )
)
print(graph.mode, graph.status, graph.unread_incoming_pages)
```

Modes are `outgoing` (default), `incoming` and `both`. Edges always point from
citing to referenced paper. Combined traversal processes outgoing references then
incoming pages at each expanded node, using one shared budget. Incoming page
failures preserve earlier records and identify the interrupted page. See the
[direction and pagination contract](src/research_bridge/knowledge_graph/README.md#incoming-and-combined-traversal).
Existing `ExploreOutgoing` imports and `/v1/graphs/outgoing` remain supported.

## Filter results and inspect evidence

```sh
uv run research-bridge explore W2741809807 --mode both --depth 2 --year-from 2018 --year-to 2025 --min-citations 0 --topic 'Graph Theory' > graph.json
curl -X POST http://localhost:8000/v1/graphs/explore -H 'Content-Type: application/json' -d '{"identifier":"W2741809807","mode":"both","filters":{"year_from":2018,"max_citations":100,"venue":"Nature"}}'
```

Optional CLI flags also include `--author`, `--venue` and `--max-citations`.
Ranges are inclusive. Names match exactly, ignoring case and whitespace; all
supplied filters combine with AND. Missing metadata fails an active filter. Invalid
filter values use HTTP 422 or CLI exit 2 with error code `invalid_filters`.
These examples may retain only the seed when the acquired neighborhood has no
matches. Filters apply after traversal, within the requested depth and budgets;
they do not query the full corpus. The seed stays, and filtered edges require
retained endpoints. Inspect `filters`, `acquired_nodes`, `acquired_edges`, `limits`
and `status` before interpreting coverage. See the
[full filter semantics](src/research_bridge/knowledge_graph/README.md#filter-returned-papers-and-inspect-evidence).

```python
from research_bridge.knowledge_graph.application import ExplorationFilters

graph = asyncio.run(
    ExploreCitations(OpenAlexPaperAdapter()).execute(
        "W2741809807",
        ExplorationLimits(depth=2),
        mode="both",
        filters=ExplorationFilters(year_from=2018, min_citations=0),
    )
)
for node in graph.nodes:
    print(node.paper.identifiers.openalex_id, node.paper.title, node.evidence.to_dict())
for edge in graph.edges:
    print(edge.source, edge.target, edge.referenced_id, edge.evidence.to_dict())
```

For CLI/HTTP JSON, select a paper from `nodes` by its canonical identifier and
inspect its metadata and source. For example, after saving the CLI result above:

```sh
jq '.nodes[] | select(.paper.identifiers.openalex_id.value == "W2741809807") | {paper, evidence}' graph.json
jq '.edges[] | {source, target, referenced_id, evidence}' graph.json
```

Every evidence record exposes its stable ID, provider record ID, source URL,
observation time and reported/inferred status. Follow `evidence.source_url` to
inspect the source record; it may have changed since observation. Citation evidence
supports the original reference assertion, including when the target was merged.

## Checks and packaging

```sh
uv run ruff check .
uv run ruff format --check .
uv run --extra server mypy
uv run --extra server pytest
uv run --extra server python scripts/export_openapi.py --check
uv build
uv run python scripts/verify_distribution.py
```

Tests cover API behavior, side-effect-free imports and inward layer dependencies.
The complete offline journey uses a synthetic HTTP provider with the real OpenAlex
adapter: paginated ambiguous titles → explicit selection → every direction at
1–3 hops → filtered paper and citation evidence inspection. It also checks DOI
entry, exhausted requests, unresolved references and failure after an incoming page.
Run it alone with `uv run --extra server pytest tests/test_complete_journey.py`.
Existing capability tests cover exact count/time limits, cancellation and retries.

`uv build` creates the wheel and source distribution, including the source archive's
usage documentation and verification fixtures. Verify the built wheel in a fresh
environment, without FastAPI, Uvicorn, Starlette or pytest (POSIX shell):

```sh
core_check_dir=$(mktemp -d)
uv venv "$core_check_dir/venv" --python 3.13
uv export --frozen --no-dev --no-emit-project --no-hashes --output-file "$core_check_dir/constraints.txt"
uv pip install --python "$core_check_dir/venv/bin/python" --constraint "$core_check_dir/constraints.txt" dist/research_bridge_core-0.1.0-py3-none-any.whl
"$core_check_dir/venv/bin/python" -I "$PWD/tests/offline_journey.py" --require-core-only
```

The standalone check exercises documented application imports and actual installed
CLI processes. `-I` prevents the checkout or `PYTHONPATH` from providing the library.
It uses only an ephemeral loopback HTTP server; dependency installation may need
network access. Verify the source distribution in a separate fresh environment,
using the journey shipped inside that archive:

```sh
source_check_dir=$(mktemp -d)
uv venv "$source_check_dir/venv" --python 3.13
uv export --frozen --no-dev --no-emit-project --no-hashes --output-file "$source_check_dir/constraints.txt"
uv pip install --python "$source_check_dir/venv/bin/python" --constraint "$source_check_dir/constraints.txt" dist/research_bridge_core-0.1.0.tar.gz
tar -xzf dist/research_bridge_core-0.1.0.tar.gz -C "$source_check_dir"
"$source_check_dir/venv/bin/python" -I "$source_check_dir/research_bridge_core-0.1.0/tests/offline_journey.py" --require-core-only
```

CI runs both clean-install checks on Python 3.13 and 3.14 with core dependencies
constrained to the frozen lockfile. Each matrix entry checks its interpreter,
types, offline tests and OpenAPI drift; the container runs once on Python 3.13.
The default development interpreter remains Python 3.13. To reproduce the matrix
locally in separate environments (POSIX shell):

```sh
compatibility_check_dir=$(mktemp -d)
for python_version in 3.13 3.14; do
  export UV_PROJECT_ENVIRONMENT="$compatibility_check_dir/python-$python_version"
  export UV_PYTHON="$python_version"
  uv sync --frozen --extra server --python "$python_version"
  uv run --frozen --extra server python -c 'import os, sys; print(sys.version); assert f"{sys.version_info.major}.{sys.version_info.minor}" == os.environ["UV_PYTHON"]'
  uv run --frozen ruff check .
  uv run --frozen ruff format --check .
  uv run --frozen --extra server mypy --python-version "$python_version"
  uv run --frozen --extra server pytest
  uv run --frozen --extra server python scripts/export_openapi.py --check
done
unset UV_PROJECT_ENVIRONMENT UV_PYTHON
```

Run the wheel and source-install commands above with each version's `--python`
value as well. The source journey must run from the extracted archive with `-I`.
`verify_distribution.py` checks archive boundaries, source parity, optional server
dependencies, console entrypoints and local documentation file links.

Offline verification establishes behavior against synthetic provider responses.
A separate bounded live smoke and manual container check passed on 2026-09-13;
see [dated verification evidence](docs/verification.md) for commands, outcomes and
limitations. This does not guarantee provider availability or corpus coverage. Provider order and metadata can change;
filters only select within the acquired neighborhood, exact names do not establish
author identity, and evidence links identify live records rather than archived
payloads. See [provider limitations](src/research_bridge/ingestion/openalex/README.md)
and [graph completeness](src/research_bridge/knowledge_graph/README.md).

Export intentional API changes with `uv run --extra server python scripts/export_openapi.py`. CI checks snapshot drift; compatibility with prior published releases must be added when releases exist. The current `0.1.0` is a local development version, not a published release.

## Container

```sh
docker build -t research-bridge-ai:local .
docker run --rm -p 8000:8000 research-bridge-ai:local
```

The image uses the frozen uv lockfile and runs under an unprivileged user. `/health`
reports process availability, not database/provider readiness. To verify actual
server startup, HTTP journeys, installed CLI commands and graceful shutdown:

```sh
uv run --extra server python tests/runtime_smoke.py
docker run --rm --network none \
  --mount "type=bind,source=$PWD/tests,target=/verification,readonly" \
  --entrypoint /app/.venv/bin/python research-bridge-ai:local /verification/runtime_smoke.py --require-unprivileged
```

The container smoke check uses its installed application, a read-only fixture mount
and loopback HTTP. `--network none` prevents external acquisition. It checks served
docs/schema, all directions/depths, filtering/evidence, invalid input, partial
failures and the server's completed shutdown after SIGTERM. CI builds and runs this
check as the image's unprivileged user; it does not deploy or publish the image.

For manual inspection, run the normal container with a localhost-only published
port, then inspect health and use the interactive API documentation:

```sh
docker run --rm -p 127.0.0.1:8000:8000 research-bridge-ai:local
# In another terminal:
curl --fail http://localhost:8000/health
# Open http://localhost:8000/docs and execute the documented research requests.
```

Research requests in the normal container access live OpenAlex. Keep explicit small
limits when checking it manually and inspect `status`/`stop_reasons`; bounded
truncation is expected for large neighborhoods. Stop the container after inspection.

## Project guide

- [Next assignments and current progress](docs/next-steps.md#next-assignments)
- [Citation Explorer completion evidence](docs/next-steps.md#completed-capability-tasks)
- [Product context](docs/product.md)
- [Architecture](docs/architecture.md)
- [Agent instructions](AGENTS.md)
- [Contract policy](contracts/README.md)
- [Source layout decision](docs/decisions/0001-capability-modules.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for commit conventions, ownership review and verification expectations. No hook installation is required.
