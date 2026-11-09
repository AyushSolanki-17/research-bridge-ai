"""FastAPI integration for standalone and embedded applications."""

from research_bridge.api.app import create_app, install_error_handlers, mount_research_bridge
from research_bridge.api.router import create_router

__all__ = [
    "create_app",
    "create_router",
    "install_error_handlers",
    "mount_research_bridge",
]
