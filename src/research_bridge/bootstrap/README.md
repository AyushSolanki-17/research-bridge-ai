# Bootstrap

`api.py` constructs the FastAPI application; `server.py` reads runtime host/port settings and launches it. Capability-owned routers are registered here. Importing `research_bridge` does not start servers or load optional web dependencies.

Keep business rules in capabilities. CLI research commands and worker execution will be added with their behavior. See [runtime commands](../../../README.md).
