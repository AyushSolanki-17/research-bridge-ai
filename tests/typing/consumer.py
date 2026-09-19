"""Check installed application exports retain concrete types for library consumers.

Copied outside the checkout and checked against each clean core installation by
scripts/verify_installation.py. No server dependencies or provider calls are needed.
"""

from typing import assert_type

from research_bridge.knowledge_graph.application import (
    ExplorationFilters,
    ExplorationLimits,
    ExplorationResult,
    ExploreCitations,
    ExploreOutgoing,
)
from research_bridge.research.papers.application import (
    PaperProviderPort,
    PaperSearchPort,
    ResolvedPaper,
    ResolvePaper,
    SearchPapers,
    SearchResult,
)


async def inspect_results(provider: PaperProviderPort, search_provider: PaperSearchPort) -> None:
    """Assert the supported contracts remain typed across an installed package boundary.

    Args:
        provider: Structural lookup implementation supplied by a consumer.
        search_provider: Independent structural title search implementation.
    """
    record = await ResolvePaper(provider).execute("W1")
    assert_type(record, ResolvedPaper)
    assert_type(record.paper.title, str | None)
    assert_type(record.evidence.source_url, str)
    assert_type(await SearchPapers(search_provider).execute("Synthetic title"), SearchResult)
    graph = await ExploreCitations(provider).execute(
        record, ExplorationLimits(depth=1), filters=ExplorationFilters(min_citations=0)
    )
    assert_type(graph, ExplorationResult)
    assert_type(await ExploreOutgoing(provider).execute(record), ExplorationResult)
