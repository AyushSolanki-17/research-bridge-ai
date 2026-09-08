# API

All FastAPI implementation lives here: application assembly, routers, HTTP schemas,
dependencies, middleware and server startup. Add modules only when behavior needs them.
Business packages outside `api/` expose framework-independent application contracts;
routes call those contracts without moving business rules into HTTP handlers.

- `app.py` creates the FastAPI application and registers routers.
- `health.py` owns the health router and immutable `HealthResponse` HTTP schema.
- `server.py` reads host/port settings and launches Uvicorn.

`GET /health` returns HTTP 200 with `{"status": "ok"}`. It reports process liveness
without checking a database or external provider. `tests/api/test_health.py` verifies
the response; `contracts/openapi.json` records the exported contract.

The independent command-line entrypoint lives in `research_bridge/cli.py`.
See the [runtime commands](../../../README.md).
