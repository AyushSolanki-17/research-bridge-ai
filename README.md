# Research Bridge AI

Explore scholarly citations with inspectable source evidence. Search for a paper,
review candidates, then follow outgoing, incoming or combined citation paths within
explicit bounds through a Python library, HTTP API or CLI.

**Python 3.13–3.14 · OpenAlex · Optional FastAPI server · Offline development tests**

Citation edges mean **citing paper → referenced paper**. Results preserve metadata,
source attribution, observation times and incomplete acquisition status. Filters
apply after traversal, within the acquired neighborhood.

[Usage examples](docs/usage.md) · [Development](docs/development.md) ·
[Extending the code](docs/extending.md) · [Architecture](docs/architecture.md) ·
[Documentation index](docs/README.md)

## Quickstart

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from
the repository root:

```sh
uv sync --frozen --extra server
uv run --frozen --extra server pytest tests/test_complete_journey.py
uv run --frozen --extra server research-bridge-ai-api
```

The test journey runs against synthetic data without credentials or external
services. The server exposes interactive docs at <http://localhost:8000/docs> and
process health at <http://localhost:8000/health>. Python 3.13 is selected by
`.python-version`; uv can provision it automatically.

With the environment installed, try the CLI:

```sh
uv run --frozen --extra server research-bridge --help
uv run --frozen --extra server research-bridge search 'The state of OA' --page-size 5
uv run --frozen --extra server research-bridge explore W2741809807 --mode both --depth 2 --max-nodes 20
```

Search and exploration access live OpenAlex. Review search candidates and explicitly
choose the identifier to explore. CLI results are JSON; exit code 5 means bounded
truncation with available results preserved. Inspect `status`, `stop_reasons` and
`unresolved` before interpreting coverage. See [all examples and exit codes](docs/usage.md).

The library and CLI also install without the `server` extra. The root project builds
one distribution, `research-bridge-core`; its Python import is `research_bridge`.
No database is required. Version `0.1.0` is a local development version, not a
published release.

## Find the owner

| Change | Start here | Responsibility |
| --- | --- | --- |
| Identifiers, paper metadata, title search | [Papers](src/research_bridge/research/papers/README.md) | Canonical values and paper use cases |
| Citation traversal, limits, filters | [Knowledge graph](src/research_bridge/knowledge_graph/README.md) | Bounded graphs, direction and partial results |
| Evidence and attribution | [Provenance](src/research_bridge/provenance/README.md) | Stable identity, sources and inference status |
| OpenAlex HTTP or payloads | [OpenAlex](src/research_bridge/ingestion/openalex/README.md) | Acquisition and canonical translation |
| HTTP routes and composition | [API](src/research_bridge/api/README.md) | Request/response contracts and server lifecycle |
| CLI commands | [cli.py](src/research_bridge/cli.py) | Arguments, composition, JSON and exit codes |

Business rules belong to their capabilities. Entrypoints compose narrow provider
protocols with concrete adapters; immutable values carry validated metadata and
results. Read the [source map](src/research_bridge/README.md) and
[worked change paths](docs/extending.md) before adding a module or abstraction.

## Checks and packaging

```sh
make setup
make check
make install-check
make smoke
```

`make check` runs Ruff lint/format checks, strict source typing, offline tests and
OpenAPI drift. `make install-check` builds and inspects wheel/source archives, then
checks clean core-only installations and installed consumer types. `make smoke`
verifies API/CLI process behavior over local sockets. CI uses the same check and
installation targets on Python 3.13 and 3.14.

Make is optional: [development commands](docs/development.md#development-loop)
include direct uv equivalents, focused tests and debugging guidance. Use
`PYTHON_VERSION=3.14` with Make to select the other supported interpreter.
See [dated verification evidence](docs/verification.md) for actual outcomes and
[known limitations](docs/next-steps.md) for remaining work.

## Container

```sh
docker build -t research-bridge-ai:local .
docker run --rm -p 127.0.0.1:8000:8000 research-bridge-ai:local
```

The image runs as an unprivileged user. See the
[container verification guide](docs/development.md#container) for an offline smoke
check, shutdown verification and manual inspection.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) for the change workflow and review criteria.
[AGENTS.md](AGENTS.md) is the shared instruction source for coding agents; tools
that do not discover it automatically should be pointed to it explicitly. Start
with a concrete behavior and its owner, add a focused regression check, and run
the relevant verification before reporting completion.
