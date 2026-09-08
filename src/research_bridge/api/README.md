# API

`app.py` creates the FastAPI application and registers capability-owned routers.
`server.py` reads host/port settings and launches Uvicorn. Business rules belong in
capabilities; these entrypoints only assemble and run the HTTP application.

The independent command-line entrypoint lives in `research_bridge/cli.py`.
See the [runtime commands](../../../README.md).
