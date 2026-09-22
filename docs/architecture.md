# Architecture

Research Bridge is a framework-independent business library with optional OpenAlex,
FastAPI, and CLI adapters. `ResearchBridge` is the public façade. It coordinates
resolution, title search, and bounded citation exploration without importing a web
framework or constructing a concrete provider.

## Package layout

```text
src/research_bridge/
  __init__.py               small supported public API
  bridge.py                 shared business façade
  core/
    identifiers.py          DOI and OpenAlex identifier parsing
    papers.py               canonical paper values
    evidence.py             source attribution and inference status
    citations.py            graph limits, results, and status values
    filters.py              metadata predicates
    budget.py               request and deadline accounting
    ports.py                provider protocols and acquisition page values
    resolution.py           identifier resolution
    search.py               bounded title candidate search
    explorer.py             breadth-first citation traversal
  providers/openalex/
    client.py               HTTP operations, retries, and pagination
    mapper.py               pure provider-payload translation
    settings.py             explicit/environment configuration
  api/
    schemas.py              HTTP request models and input translation
    router.py               injectable router factory
    errors.py               application-error to HTTP translation
    health.py               process-liveness route
    app.py                  standalone composition and embedding helpers
    server.py               Uvicorn command entrypoint
  cli.py                    command-line adapter over ResearchBridge
```

The package deliberately does not use nested `domain/application/infrastructure`
folders. At this size, explicit modules and one dependency boundary are easier to
navigate and enforce.

## Dependency direction

```text
FastAPI / CLI ──> ResearchBridge ──> core operations and ports
       │                                  ▲
       └──────── OpenAlex provider ───────┘
```

- `core/` and `bridge.py` contain business behavior and cannot import FastAPI,
  Pydantic, HTTPX, Uvicorn, CLI, or provider implementations.
- `providers/` implement core-owned ports and map external data into core values.
- `api/router.py` receives a configured `ResearchBridge`; it never selects a provider.
- Only `api/app.py` and `cli.py` choose OpenAlex for their standalone defaults.
- External FastAPI applications mount `create_router(bridge)` or call
  `mount_research_bridge(app, bridge)`.

Static checks in `tests/test_architecture.py` enforce these rules against real imports.

## Public business API

Library consumers import `ResearchBridge` and common request/result values from the
package root. More specialized models and provider protocols are available from
`research_bridge.core`. Concrete OpenAlex configuration is available from
`research_bridge.providers.openalex`.

The façade exists to keep construction consistent across Python, HTTP, and CLI. It
does not duplicate business rules: resolution, search, filtering, traversal, and
budgets remain in focused core modules.

## FastAPI embedding

```python
from fastapi import FastAPI

from research_bridge import ResearchBridge
from research_bridge.api import mount_research_bridge
from research_bridge.providers.openalex import OpenAlexProvider

app = FastAPI()
mount_research_bridge(app, ResearchBridge(OpenAlexProvider()), prefix="/research/v1")
```

The router uses closures around the supplied façade. It does not write dependencies
to `app.state`, construct OpenAlex clients, or place research decisions in Pydantic
validators. HTTP schemas only enforce transport shape and translate into core values.

## Runtime semantics

One operation-scoped budget counts physical requests, redirects, retries, and elapsed
time. Citation traversal is breadth-first and bounded by depth, nodes, edges, requests,
and time. Results explicitly distinguish complete, truncated, and failed acquisition.
Metadata filters run after traversal. Evidence preserves provider identity, source URL,
observation time, and inference status. Citation edges mean references, not influence.

OpenAlex is the only implemented provider and canonical work identities are currently
OpenAlex work IDs. Supporting records without an OpenAlex identity is a deliberate
public-model change, not an adapter-only addition.

## Distribution

The repository builds one typed distribution. FastAPI and Uvicorn remain optional
server dependencies; importing `research_bridge` does not load them or start services.
The core, CLI, and OpenAlex provider remain usable without the server extra. There is
no database, queue, cache, provider registry, service locator, or plugin framework.
