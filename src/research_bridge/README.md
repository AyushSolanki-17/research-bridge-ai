# research_bridge

Application source root for one installable distribution. The top-level import exposes a version without importing FastAPI or starting services. `api/app.py` assembles health and versioned research routes. The library and CLI implement identifier resolution, title candidate search and bounded outgoing, incoming and combined citation exploration with metadata filtering and inspectable paper/source evidence. See [architecture](../../docs/architecture.md).
