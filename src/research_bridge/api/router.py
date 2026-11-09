"""FastAPI router factory adapting HTTP requests to a ResearchBridge instance."""

from fastapi import APIRouter, Response

from research_bridge import ResearchBridge
from research_bridge.api.errors import ErrorResponse
from research_bridge.api.schemas import (
    CitationExploreRequest,
    ExploreRequest,
    ResolveRequest,
    SearchRequest,
)
from research_bridge.core import ExplorationResult, ResolvedPaper, SearchResult


def _set_graph_status(response: Response, result: ExplorationResult) -> None:
    """Map a failed partial graph to its transport status code."""
    if result.status == "failed":
        response.status_code = 404 if "seed_not_found" in result.stop_reasons else 502


def create_router(bridge: ResearchBridge, *, prefix: str = "/v1") -> APIRouter:
    """Create an injectable router for mounting in any FastAPI application.

    Args:
        bridge: Framework-independent business façade called by every endpoint.
        prefix: URL prefix applied to the research operations.

    Returns:
        Router with no global state or provider construction.
    """
    router = APIRouter(
        prefix=prefix,
        tags=["research"],
        responses={status: {"model": ErrorResponse} for status in (404, 422, 429, 502, 504)},
    )

    @router.post("/papers/resolve", response_model=ResolvedPaper, operation_id="resolve_paper")
    async def resolve_paper(body: ResolveRequest) -> ResolvedPaper:
        """Resolve a DOI or work identifier to canonical metadata and evidence."""
        return await bridge.resolve(body.identifier)

    @router.post(
        "/graphs/outgoing",
        response_model=ExplorationResult,
        operation_id="explore_outgoing",
        responses={
            404: {"model": ExplorationResult, "description": "Seed not found."},
            502: {"model": ExplorationResult, "description": "Provider failure with partial data."},
        },
    )
    async def explore_outgoing(body: ExploreRequest, response: Response) -> ExplorationResult:
        """Return an outgoing neighborhood with explicit scope and completion status."""
        result = await bridge.explore(
            body.identifier,
            body.limits.to_core(),
            filters=body.filters.to_core() if body.filters else None,
        )
        _set_graph_status(response, result)
        return result

    @router.post(
        "/graphs/explore",
        response_model=ExplorationResult,
        operation_id="explore_citations",
        responses={
            404: {"model": ExplorationResult, "description": "Seed not found."},
            502: {"model": ExplorationResult, "description": "Provider failure with partial data."},
        },
    )
    async def explore_citations(
        body: CitationExploreRequest, response: Response
    ) -> ExplorationResult:
        """Return a bounded neighborhood in the requested citation directions."""
        result = await bridge.explore(
            body.identifier,
            body.limits.to_core(),
            mode=body.mode,
            filters=body.filters.to_core() if body.filters else None,
        )
        _set_graph_status(response, result)
        return result

    @router.post(
        "/papers/search",
        response_model=SearchResult,
        operation_id="search_papers",
        responses={
            502: {"model": SearchResult, "description": "Provider failure with partial candidates."}
        },
    )
    async def search_papers(body: SearchRequest, response: Response) -> SearchResult:
        """Review an attributed candidate page; select an identifier to resolve or explore."""
        result = await bridge.search(body.query, body.limits.to_core(), page=body.page)
        if result.status == "failed":
            response.status_code = 502
        return result

    return router
