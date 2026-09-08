# API contracts

`openapi.json` is exported deterministically from the implemented FastAPI app. It currently describes only `GET /health`.

```sh
uv run --extra server python scripts/export_openapi.py
uv run --extra server python scripts/export_openapi.py --check
```

CI fails on unexported schema drift. No published schema release or compatibility baseline exists yet; add release compatibility checks before the first consumer upgrade. Consumer-facing research APIs must preserve stable errors, evidence identifiers, pagination, bounds and partial-result semantics.

Research Bridge UI will generate a client from a pinned released schema when the first API-consuming feature lands. Record schema checksums and generator versions; do not guess models from a development server.
