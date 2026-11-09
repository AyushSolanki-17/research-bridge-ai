"""HTTP-only request schemas and translation into business inputs."""

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt

from research_bridge.core import (
    ExplorationFilters,
    ExplorationLimits,
    ExplorationMode,
    SearchLimits,
)

_exploration_defaults = ExplorationLimits()
_search_defaults = SearchLimits()


class ResolveRequest(BaseModel):
    """Identifier lookup input; unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")
    identifier: str = Field(min_length=1, max_length=2048)


class LimitsRequest(BaseModel):
    """HTTP budget types; the application owns numeric bounds and validation."""

    model_config = ConfigDict(extra="forbid")
    depth: StrictInt = Field(
        default=_exploration_defaults.depth, description="Citation hops: 1 through 3."
    )
    max_nodes: StrictInt = Field(
        default=_exploration_defaults.max_nodes, description="Papers: 1 through 500."
    )
    max_edges: StrictInt = Field(
        default=_exploration_defaults.max_edges, description="Edges: 1 through 2000."
    )
    max_requests: StrictInt = Field(
        default=_exploration_defaults.max_requests,
        description="Physical requests: 1 through 1000.",
    )
    max_seconds: StrictFloat = Field(
        default=_exploration_defaults.max_seconds,
        description="Finite elapsed seconds: greater than 0, at most 120.",
    )

    def to_core(self) -> ExplorationLimits:
        """Translate the transport value into validated business limits."""
        return ExplorationLimits(**self.model_dump())


class FiltersRequest(BaseModel):
    """Metadata predicates; application contracts own matching and range validation."""

    model_config = ConfigDict(extra="forbid")
    year_from: StrictInt | None = Field(default=None, description="Inclusive year: 1–9999.")
    year_to: StrictInt | None = Field(default=None, description="Inclusive year: 1–9999.")
    min_citations: StrictInt | None = Field(
        default=None, description="Inclusive count, at least 0."
    )
    max_citations: StrictInt | None = Field(
        default=None, description="Inclusive count, at least 0."
    )
    author: str | None = Field(
        default=None, max_length=300, description="Exact author display name."
    )
    venue: str | None = Field(default=None, max_length=300, description="Exact venue display name.")
    topic: str | None = Field(default=None, max_length=300, description="Exact topic display name.")

    def to_core(self) -> ExplorationFilters:
        """Translate the transport value into normalized business predicates."""
        return ExplorationFilters(**self.model_dump())


class ExploreRequest(ResolveRequest):
    """Outgoing exploration input with optional bounded overrides."""

    limits: LimitsRequest = Field(default_factory=LimitsRequest)
    filters: FiltersRequest | None = Field(
        default=None,
        description="Filter returned papers after bounded traversal; always retain the seed.",
    )


class CitationExploreRequest(ExploreRequest):
    """Citation exploration direction with the same shared operation bounds."""

    mode: ExplorationMode = "outgoing"


class SearchLimitsRequest(BaseModel):
    """Search budget types; application contracts validate numeric bounds."""

    model_config = ConfigDict(extra="forbid")
    page_size: StrictInt = _search_defaults.page_size
    max_results: StrictInt = _search_defaults.max_results
    max_requests: StrictInt = _search_defaults.max_requests
    max_seconds: StrictFloat = _search_defaults.max_seconds

    def to_core(self) -> SearchLimits:
        """Translate the transport value into validated business limits."""
        return SearchLimits(**self.model_dump())


class SearchRequest(BaseModel):
    """Title text and one-based candidate page, without automatic seed selection."""

    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=300)
    page: StrictInt = 1
    limits: SearchLimitsRequest = Field(default_factory=SearchLimitsRequest)
