"""Versioned research request schemas, dependencies and thin HTTP handlers."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt

from research_bridge.knowledge_graph.application import (
    ExplorationLimits,
    ExplorationResult,
    ExploreOutgoing,
)
from research_bridge.research.papers.application import (
    ResolvedPaper,
    ResolvePaper,
    SearchLimits,
    SearchPapers,
    SearchResult,
)

router = APIRouter(prefix="/v1", tags=["research"])
_defaults = ExplorationLimits()


class ResolveRequest(BaseModel):
    """Identifier lookup input; unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")
    identifier: str = Field(min_length=1, max_length=2048)


class LimitsRequest(BaseModel):
    """HTTP budget types; the application owns numeric bounds and validation."""

    model_config = ConfigDict(extra="forbid")
    depth: StrictInt = Field(default=_defaults.depth, description="Citation hops: 1 through 3.")
    max_nodes: StrictInt = Field(default=_defaults.max_nodes, description="Papers: 1 through 500.")
    max_edges: StrictInt = Field(default=_defaults.max_edges, description="Edges: 1 through 2000.")
    max_requests: StrictInt = Field(
        default=_defaults.max_requests, description="Physical requests: 1 through 1000."
    )
    max_seconds: StrictFloat = Field(
        default=_defaults.max_seconds,
        description="Finite elapsed seconds: greater than 0, at most 120.",
    )

    def to_application(self) -> ExplorationLimits:
        """Build validated application bounds, raising ValueError for invalid limits."""
        return ExplorationLimits(**self.model_dump())


class ExploreRequest(ResolveRequest):
    """Outgoing exploration input with optional bounded overrides."""

    limits: LimitsRequest = Field(default_factory=LimitsRequest)


def get_resolver(request: Request) -> ResolvePaper:
    """Return the resolver composed by this application instance."""
    return cast(ResolvePaper, request.app.state.resolver)


def get_explorer(request: Request) -> ExploreOutgoing:
    """Return the explorer composed by this application instance."""
    return cast(ExploreOutgoing, request.app.state.explorer)


@router.post("/papers/resolve", response_model=ResolvedPaper, operation_id="resolve_paper")
async def resolve_paper(
    body: ResolveRequest, resolver: Annotated[ResolvePaper, Depends(get_resolver)]
) -> ResolvedPaper:
    """Resolve a DOI or work identifier to canonical metadata and evidence."""
    return await resolver.execute(body.identifier)


@router.post(
    "/graphs/outgoing",
    response_model=ExplorationResult,
    operation_id="explore_outgoing",
    responses={
        404: {"model": ExplorationResult, "description": "Seed not found."},
        502: {"model": ExplorationResult, "description": "Provider failure with partial data."},
    },
)
async def explore_outgoing(
    body: ExploreRequest,
    response: Response,
    explorer: Annotated[ExploreOutgoing, Depends(get_explorer)],
) -> ExplorationResult:
    """Return an outgoing neighborhood with explicit scope and completion status."""
    result = await explorer.execute(body.identifier, body.limits.to_application())
    if result.status == "failed":
        response.status_code = 404 if "seed_not_found" in result.stop_reasons else 502
    return result


class SearchLimitsRequest(BaseModel):
    """Search budget types; application contracts validate numeric bounds."""

    model_config = ConfigDict(extra="forbid")
    page_size: StrictInt = SearchLimits().page_size
    max_results: StrictInt = SearchLimits().max_results
    max_requests: StrictInt = SearchLimits().max_requests
    max_seconds: StrictFloat = SearchLimits().max_seconds


class SearchRequest(BaseModel):
    """Title text and one-based candidate page, without automatic seed selection."""

    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=300)
    page: StrictInt = 1
    limits: SearchLimitsRequest = Field(default_factory=SearchLimitsRequest)


def get_searcher(request: Request) -> SearchPapers:
    """Return the title search use case composed by the application."""
    return cast(SearchPapers, request.app.state.searcher)


@router.post(
    "/papers/search",
    response_model=SearchResult,
    operation_id="search_papers",
    responses={
        502: {"model": SearchResult, "description": "Provider failure with partial candidates."}
    },
)
async def search_papers(
    body: SearchRequest,
    response: Response,
    searcher: Annotated[SearchPapers, Depends(get_searcher)],
) -> SearchResult:
    """Review an attributed candidate page; select an identifier to resolve or explore."""
    result = await searcher.execute(
        body.query, SearchLimits(**body.limits.model_dump()), page=body.page
    )
    if result.status == "failed":
        response.status_code = 502
    return result
