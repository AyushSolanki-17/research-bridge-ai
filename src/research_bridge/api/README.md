# FastAPI integration

This package is an outer transport adapter over `ResearchBridge`.

- `schemas.py` owns HTTP request models and conversion to core inputs.
- `router.py` creates routes around an injected business façade.
- `errors.py` maps expected core failures to safe HTTP responses.
- `health.py` reports process liveness.
- `app.py` mounts the router and supplies OpenAlex only for the standalone service.
- `server.py` launches Uvicorn for the installed command.

Routes do not construct providers, store services in `app.state`, or implement
identifier, search, filter, traversal, or status rules.

## Embed in another FastAPI application

```python
from fastapi import FastAPI

from research_bridge import ResearchBridge
from research_bridge.api import mount_research_bridge
from research_bridge.providers.openalex import OpenAlexProvider

app = FastAPI()
mount_research_bridge(app, ResearchBridge(OpenAlexProvider()), prefix="/research/v1")
```

For separate control, call `install_error_handlers(app)` and then
`app.include_router(create_router(bridge, prefix="/research/v1"))`.

## Routes

| Route | Operation |
| --- | --- |
| `GET /health` | Standalone process liveness |
| `POST /v1/papers/resolve` | Resolve an identifier |
| `POST /v1/papers/search` | Review title candidates |
| `POST /v1/graphs/outgoing` | Compatible outgoing-only exploration |
| `POST /v1/graphs/explore` | Outgoing, incoming, or combined exploration |

Research operations are read-only and bounded. Complete or truncated results return
HTTP 200. Missing graph seeds return 404 with the partial graph; other graph provider
failures return 502. Invalid business input returns a safe 422 envelope. Rate limits,
timeouts, malformed provider data, and exhausted retries map to 429, 504, or 502.

See [core semantics](../core/README.md), [usage](../../../docs/usage.md), and the
checked [OpenAPI contract](../../../contracts/openapi.json).
