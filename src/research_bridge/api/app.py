"""Create the HTTP application without starting a server on import."""

from fastapi import FastAPI

from research_bridge import __version__
from research_bridge.system.interfaces.api import router as system_router


def create_app() -> FastAPI:
    """Assemble an independent application instance with capability-owned routes."""
    app = FastAPI(title="Research Bridge API", version=__version__)
    app.include_router(system_router)
    return app
