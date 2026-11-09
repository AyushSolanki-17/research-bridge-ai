"""Public business façade shared by Python, HTTP, and command-line consumers."""

import time
from collections.abc import Callable

from research_bridge.core import (
    ExplorationFilters,
    ExplorationLimits,
    ExplorationMode,
    ExplorationResult,
    ExploreCitations,
    IncomingCitationPort,
    PaperProviderPort,
    PaperSearchPort,
    ResolvedPaper,
    ResolvePaper,
    SearchLimits,
    SearchPapers,
    SearchResult,
    UnsupportedOperationError,
)


class ResearchBridge:
    """Coordinate reusable research operations without a transport dependency.

    The façade is the supported integration point for Python and web applications.
    Providers remain injected, while identifier parsing, search paging, citation
    traversal, filtering, and partial-result semantics stay inside the core package.
    """

    def __init__(
        self,
        provider: PaperProviderPort,
        *,
        search_provider: PaperSearchPort | None = None,
        incoming_provider: IncomingCitationPort | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Compose supported operations around caller-owned provider ports.

        Args:
            provider: Paper lookup provider used by resolution and traversal.
            search_provider: Optional title-search provider. A provider that
                structurally implements the search port is selected automatically.
            incoming_provider: Optional incoming-citation provider. The explorer
                selects the lookup provider automatically when it implements the port.
            clock: Monotonic clock shared by bounded search and exploration.
        """
        if search_provider is None and isinstance(provider, PaperSearchPort):
            search_provider = provider
        self._resolver = ResolvePaper(provider)
        self._searcher = SearchPapers(search_provider, clock=clock) if search_provider else None
        self._explorer = ExploreCitations(
            provider, incoming_provider=incoming_provider, clock=clock
        )

    async def resolve(self, identifier: str) -> ResolvedPaper:
        """Resolve a DOI or OpenAlex work identifier."""
        return await self._resolver.execute(identifier)

    async def search(
        self, query: str, limits: SearchLimits | None = None, *, page: int = 1
    ) -> SearchResult:
        """Return title candidates without implicitly selecting one."""
        if self._searcher is None:
            raise UnsupportedOperationError("title search is not configured")
        return await self._searcher.execute(query, limits, page=page)

    async def explore(
        self,
        seed: str | ResolvedPaper,
        limits: ExplorationLimits | None = None,
        *,
        mode: ExplorationMode = "outgoing",
        filters: ExplorationFilters | None = None,
    ) -> ExplorationResult:
        """Explore a bounded citation neighborhood in the requested directions."""
        return await self._explorer.execute(seed, limits, mode=mode, filters=filters)
