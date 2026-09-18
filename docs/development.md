# Development guide

Use this guide for local commands, focused tests and troubleshooting. For code
placement and worked change paths, read [extending the code](extending.md).
[AGENTS.md](../AGENTS.md) applies to human and automated contributions alike.

## Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then from the
repository root run `make setup`. Python 3.13 is the default; uv can provision it.
Python 3.14 is also supported. Make is an optional convenience for POSIX systems;
the underlying commands below also work without Make.

Configure your editor to use `.venv/bin/python` (`.venv/Scripts/python.exe` on
Windows). Ruff owns formatting and linting; mypy is the authoritative type check.
Editor extensions are optional. The repository's `.editorconfig` defines whitespace.

The setup command installs the optional server stack and development tools.
Core-only consumers need only the root distribution. No database, API key or
external service is needed for the normal tests after dependencies are installed.

## Development loop

```sh
make setup
uv run --frozen --extra server pytest tests/knowledge_graph -q
make format
make check
```

`make check` is also CI's code/contract gate. It runs sequentially and fails on the
first unsuccessful command. It does not edit source or regenerate the schema.
Keep the `server` extra on development runs to avoid uv removing it from the
project environment when switching between checks. Frozen commands use the
committed lockfile; intentional dependency updates must update and review it.
See [uv's sync behavior](https://docs.astral.sh/uv/concepts/projects/sync/).

| Task | Shortcut | Underlying command |
| --- | --- | --- |
| Install development environment | `make setup` | `uv sync --frozen --extra server --python 3.13` |
| Lint | `make lint` | `uv run --frozen --extra server ruff check .` |
| Check formatting | `make format-check` | `uv run --frozen --extra server ruff format --check .` |
| Format | `make format` | `uv run --frozen --extra server ruff format .` |
| Check source types | `make types` | `uv run --frozen --extra server mypy --python-version 3.13` |
| Run offline tests | `make test` | `uv run --frozen --extra server pytest` |
| Check HTTP schema drift | `make schema` | `uv run --frozen --extra server python scripts/export_openapi.py --check` |
| Reloading development API | `make api` | `uv run --frozen --extra server uvicorn research_bridge.api.app:create_app --factory --reload --port 8000` |
| Process startup and shutdown | `make smoke` | `uv run --frozen --extra server python tests/runtime_smoke.py` |
| Build and inspect archives | `make dist` | `uv build`, then `uv run --frozen --extra server python scripts/verify_distribution.py` |
| Check installed artifacts | `make install-check` | Build/inspect, then `uv run --frozen --extra server python scripts/verify_installation.py --python 3.13` |

Run a complete fixture-backed journey alone with:

```sh
uv run --frozen --extra server pytest tests/test_complete_journey.py
```

See the [test guide](../tests/README.md) for capability suites. Use `-k NAME` to
select a behavior and `--pdb -x` to stop at the first failing test in a debugger.
Use mock transports and injected clocks when reproducing limits or cancellation.
Do not rely on live OpenAlex responses to debug deterministic business behavior.

For an intentional HTTP contract change, export using
`uv run --frozen --extra server python scripts/export_openapi.py`, then review
`contracts/openapi.json` and rerun the drift check. Export is deliberately separate
from `make check` so tests cannot silently accept a contract change.

## Configuration

`RB_HOST` defaults to `127.0.0.1`; `RB_PORT` defaults to `8000`. The installed
`research-bridge-ai-api` command reads these values. `make api` uses Uvicorn's
explicit development flags instead; change its `--port` argument when needed.

[.env.example](../.env.example) lists optional settings. Copy it to `.env` if useful
and load it explicitly:

```sh
uv run --frozen --env-file .env --extra server research-bridge-ai-api
```

Dotenv files are not loaded implicitly. Keep credentials out of fixtures and logs.
See [OpenAlex settings](../src/research_bridge/ingestion/openalex/README.md) for
provider timeouts, finite retries and optional credentials.

## Checks and packaging

Before completing executable changes, run `make check`, `make install-check` and
`make smoke`. Changes to the container also require the container checks below.
Report checks actually run and distinguish local results from remote CI.

The installation check creates temporary core-only environments for the wheel and
source archive, constrains dependencies to the frozen lockfile, and runs isolated
library/CLI journeys. The source journey comes from the extracted archive. It
asserts that FastAPI, Starlette, Uvicorn and pytest are absent, checks the selected
interpreter, and checks a typed consumer outside the checkout against each install.
Temporary environments are removed automatically. Downloads may require networking;
the verification journeys only use an ephemeral loopback HTTP provider.

`src/research_bridge/py.typed` ships inline type information for installed consumers,
as required by the [Python typing specification](https://typing.python.org/en/latest/spec/distributing.html#packaging-type-information).
Archive inspection verifies that marker, source parity, optional server dependencies,
console entrypoints and local documentation file links. The current `0.1.0` is a
local development version, not a published release.

CI runs `make check` and `make install-check` on Python 3.13 and 3.14, and builds and
smokes the container once on 3.13. CI can also be started manually. Reproduce the
interpreter checks in separate environments (POSIX shell):

```sh
compatibility_check_dir=$(mktemp -d)
for python_version in 3.13 3.14; do
  UV_PROJECT_ENVIRONMENT="$compatibility_check_dir/python-$python_version" \
    make setup check install-check smoke PYTHON_VERSION="$python_version"
done
```

Keep the printed temporary directory while diagnosing a failure; remove it when
done. These commands do not alter `.python-version` or the default `.venv`.

## Troubleshooting

| Symptom | First check |
| --- | --- |
| `uv` is missing | Install uv using its official instructions linked above. |
| `make` is unavailable | Run the underlying commands in the table; Make is not a runtime dependency. |
| API import fails | Run `uv sync --frozen --extra server`; select the project's interpreter in your editor. |
| An unexpected interpreter is selected | Check `uv run --frozen --extra server python --version`; use `PYTHON_VERSION=3.14` for Make or `UV_PYTHON=3.14` for direct uv commands. |
| Port 8000 is busy | Use the direct Uvicorn command with a different `--port`, or set `RB_PORT` for the installed API command. |
| Schema drift fails | Inspect the diff; export only if the public change is intentional. |
| Dependency resolution or installation fails | Inspect the actual uv error and manifest/lockfile difference; resolve intentional dependency changes with `uv lock`. |
| Provider-dependent command fails | Run the offline journey first, then inspect bounded provider settings and the returned error/status. |
| Docker cannot connect | Start a working local daemon; report container verification as unavailable if it remains inaccessible. |
| Starlette emits the AnyIO alias warning | See the [tracked upstream dependency issue](next-steps.md); do not suppress it. |

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
