"""Standalone FastAPI application assembly."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from research_bridge import ResearchBridge, __version__
from research_bridge.api.errors import ERRORS, invalid_request, research_error
from research_bridge.api.health import router as health_router
from research_bridge.api.router import create_router
from research_bridge.providers.openalex import OpenAlexProvider


def install_error_handlers(app: FastAPI) -> None:
    """Install Research Bridge exception translation on a FastAPI application."""
    for error_type in ERRORS:
        app.add_exception_handler(error_type, research_error)
    app.add_exception_handler(RequestValidationError, invalid_request)


def mount_research_bridge(app: FastAPI, bridge: ResearchBridge, *, prefix: str = "/v1") -> None:
    """Mount Research Bridge routes and error handling into an existing application."""
    install_error_handlers(app)
    app.include_router(create_router(bridge, prefix=prefix))


def create_app(bridge: ResearchBridge | None = None) -> FastAPI:
    """Create the standalone service around an injected business façade.

    Args:
        bridge: Business façade. The standalone default uses one OpenAlex provider.

    Returns:
        Application with health and versioned research routes.
    """
    app = FastAPI(title="Research Bridge API", version=__version__)
    bridge = bridge or ResearchBridge(OpenAlexProvider())
    app.include_router(health_router)
    mount_research_bridge(app, bridge)
    return app
