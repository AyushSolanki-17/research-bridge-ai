"""Create the HTTP application without starting a server on import."""

from fastapi import FastAPI

from research_bridge import __version__
from research_bridge.api.health import router as health_router


def create_app() -> FastAPI:
    """Assemble an independent application instance with API-owned routes."""
    app = FastAPI(title="Research Bridge API", version=__version__)
    app.include_router(health_router)
    return app
