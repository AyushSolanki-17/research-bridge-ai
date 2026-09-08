# research_bridge

Application source root for one installable distribution. The top-level import exposes a version without importing FastAPI or starting services. `api/app.py` assembles the process-health API. The library implements identifier resolution, paper metadata and provenance through the OpenAlex adapter; citation exploration remains unimplemented. See [architecture](../../docs/architecture.md).
