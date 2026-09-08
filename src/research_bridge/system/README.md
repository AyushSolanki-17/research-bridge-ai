# System

Owns operational HTTP endpoints. `interfaces/api.py` exposes `GET /health`, returning
HTTP 200 with `{"status": "ok"}` as JSON. It requires no authentication, configuration,
database or external provider. This is process liveness, not dependency readiness.

`HealthResponse` is the immutable, typed response contract. The router handles HTTP;
the application factory in `api/app.py` registers it. No domain rule, state or
external operation needs an application service or additional layer for this endpoint.

Run with the [root runtime commands](../../../README.md). `tests/test_api.py` verifies
the health response and OpenAPI operation; `contracts/openapi.json` records the schema.
