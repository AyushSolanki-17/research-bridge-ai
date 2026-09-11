"""Create the HTTP application without starting a server on import."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from research_bridge import __version__
from research_bridge.api.errors import ERRORS, ErrorResponse, invalid_request, research_error
from research_bridge.api.health import router as health_router
from research_bridge.api.research import router as research_router
from research_bridge.ingestion.openalex.infrastructure.openalex_adapter import OpenAlexPaperAdapter
from research_bridge.knowledge_graph.application import ExploreCitations, IncomingCitationPort
from research_bridge.research.papers.application import (
    PaperProviderPort,
    PaperSearchPort,
    ResolvePaper,
    SearchPapers,
)


def create_app(
    provider: PaperProviderPort | None = None,
    *,
    search_provider: PaperSearchPort | None = None,
    incoming_provider: IncomingCitationPort | None = None,
) -> FastAPI:
    """Compose research use cases and HTTP routes without acquiring data.

    Args:
        provider: Optional lookup provider for offline testing; defaults to OpenAlex.
        search_provider: Optional title search provider; defaults to OpenAlex.
        incoming_provider: Optional incoming provider; otherwise use lookup if supported.

    Returns:
        Application with health and versioned research routes.
    """
    app = FastAPI(title="Research Bridge API", version=__version__)
    acquisition = provider if provider is not None else OpenAlexPaperAdapter()
    app.state.searcher = SearchPapers(
        search_provider if search_provider is not None else OpenAlexPaperAdapter()
    )
    app.state.resolver = ResolvePaper(acquisition)
    app.state.explorer = ExploreCitations(acquisition, incoming_provider=incoming_provider)
    for error_type in ERRORS:
        app.add_exception_handler(error_type, research_error)
    app.add_exception_handler(RequestValidationError, invalid_request)
    app.include_router(health_router)
    app.include_router(
        research_router,
        responses={status: {"model": ErrorResponse} for status in (404, 422, 429, 502, 504)},
    )
    return app
