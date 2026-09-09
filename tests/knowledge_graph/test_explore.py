"""Synthetic citation neighborhoods and exact operation boundaries."""

import asyncio
from datetime import UTC, datetime

import pytest

from research_bridge.knowledge_graph.application import (
    ExplorationCancelled,
    ExplorationLimits,
    ExploreOutgoing,
)
from research_bridge.provenance.domain.evidence import Evidence
from research_bridge.research.papers.application import AcquisitionBudget, ResolvedPaper
from research_bridge.research.papers.application.errors import (
    PaperNotFoundError,
    ProviderMalformedResponseError,
)
from research_bridge.research.papers.domain.identifiers import Doi, OpenAlexWorkId
from research_bridge.research.papers.domain.paper import Paper, PaperIdentifiers


class Clock:
    """Manually advanced monotonic time for deterministic budget tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def paper(work: str, *references: str, complete: bool = True) -> ResolvedPaper:
    """Create a synthetic reported work with an explicit reference-list status."""
    return ResolvedPaper(
        Paper(
            PaperIdentifiers(OpenAlexWorkId(work)),
            title=work,
            referenced_works=tuple(OpenAlexWorkId(ref) for ref in references),
            references_complete=complete,
        ),
        Evidence.paper_evidence(work, observed_at=datetime(2026, 9, 8, tzinfo=UTC)),
    )


class Provider:
    """Budget-aware fake with observable requests and controlled elapsed time."""

    def __init__(
        self,
        records: dict[str, ResolvedPaper | BaseException],
        clock: Clock | None = None,
        duration: float = 0,
    ) -> None:
        self.records = records
        self.calls: list[str] = []
        self.clock = clock
        self.duration = duration

    async def fetch_paper(
        self, identifier: Doi | OpenAlexWorkId, *, budget: AcquisitionBudget | None = None
    ) -> ResolvedPaper:
        """Consume one request before returning a record or configured failure."""
        if budget:
            budget.consume_request()
        self.calls.append(str(identifier))
        if self.clock:
            self.clock.now += self.duration
        record = self.records.get(str(identifier), PaperNotFoundError(str(identifier)))
        if isinstance(record, BaseException):
            raise record
        return record


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "depth,expected",
    [(1, ["W1", "W2", "W3"]), (2, ["W1", "W2", "W3", "W4"]), (3, ["W1", "W2", "W3", "W4", "W5"])],
)
async def test_breadth_first_depth_cycles_and_evidence(depth: int, expected: list[str]) -> None:
    """Respect hop depth, lexical ordering, cycles, deduplication and source evidence."""
    provider = Provider(
        {
            "W1": paper("W1", "W3", "W2", "W2"),
            "W2": paper("W2", "W1", "W4"),
            "W3": paper("W3", "W4"),
            "W4": paper("W4", "W5"),
            "W5": paper("W5"),
        }
    )
    result = await ExploreOutgoing(provider).execute("W1", ExplorationLimits(depth=depth))
    assert provider.calls == expected
    assert result.status == "complete"
    assert [str(node.paper.identifiers.openalex_id) for node in result.nodes] == expected
    assert len({(edge.source, edge.target) for edge in result.edges}) == len(result.edges)
    first = result.edges[0]
    assert (str(first.source), str(first.target)) == ("W1", "W2")
    assert first.evidence.id == "openalex:citation:W1:W2"
    assert first.evidence.source_url == result.nodes[0].evidence.source_url
    assert first.evidence.observed_at == result.nodes[0].evidence.observed_at
    assert first.evidence.inference_status.value == "reported"


@pytest.mark.asyncio
@pytest.mark.parametrize("seed", ["W1", "W9"])
async def test_empty_neighborhood_and_ingested_seed(seed: str) -> None:
    """A known leaf is complete; a supplied seed consumes a node but no request."""
    provider = Provider({})
    result = await ExploreOutgoing(provider).execute(paper(seed), ExplorationLimits(max_nodes=1))
    assert result.status == "complete"
    assert result.requests == 0
    assert len(result.nodes) == 1
    assert not result.edges


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,limited,exact,reason",
    [
        ("max_nodes", 1, 2, "nodes"),
        ("max_edges", 1, 2, "edges"),
        ("max_requests", 1, 2, "requests"),
    ],
)
async def test_exact_count_boundaries(field: str, limited: int, exact: int, reason: str) -> None:
    """Stop before exceeding a limit, but complete at an exactly sufficient limit."""
    records = {"W1": paper("W1", "W2"), "W2": paper("W2", "W1")}
    for bound, status in [(limited, "truncated"), (exact, "complete")]:
        provider = Provider(records)
        result = await ExploreOutgoing(provider).execute(
            "W1", ExplorationLimits(depth=2, **{field: bound})
        )
        assert result.status == status
        if status == "truncated":
            assert reason in result.stop_reasons
            assert result.unresolved[-1].reason == reason
        assert len(result.nodes) <= result.limits.max_nodes
        assert len(result.edges) <= result.limits.max_edges
        assert result.requests <= result.limits.max_requests


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "duration,status", [(0.49, "complete"), (0.5, "truncated"), (0.51, "truncated")]
)
async def test_elapsed_boundary_with_controlled_clock(duration: float, status: str) -> None:
    """Count seed acquisition and reject a target arriving at or after the deadline."""
    clock = Clock()
    provider = Provider({"W1": paper("W1", "W2"), "W2": paper("W2")}, clock, duration)
    result = await ExploreOutgoing(provider, clock=clock).execute(
        "W1", ExplorationLimits(max_seconds=1)
    )
    assert result.status == status
    if status == "truncated":
        assert result.stop_reasons == ("elapsed_time",)
        assert len(result.nodes) == 1


@pytest.mark.asyncio
async def test_missing_reference_and_incomplete_metadata() -> None:
    """Retain asserted edges to missing works and distinguish unknown reference lists."""
    provider = Provider({"W1": paper("W1", "W2", "W3"), "W3": paper("W3", complete=False)})
    result = await ExploreOutgoing(provider).execute("W1", ExplorationLimits(depth=2))
    assert result.status == "truncated"
    assert set(result.stop_reasons) == {"unresolved_references", "incomplete_references"}
    assert result.unresolved[0].target == "W2"
    assert result.unresolved[0].reason == "not_found"
    assert len(result.edges) == 2
    assert "referenced_works" in result.incomplete_metadata[-1].fields
    assert "abstract" in result.incomplete_metadata[0].fields


@pytest.mark.asyncio
async def test_provider_failure_preserves_partial_graph() -> None:
    """An upstream failure never discards prior nodes or reports completeness."""
    provider = Provider(
        {
            "W1": paper("W1", "W2", "W3"),
            "W2": paper("W2"),
            "W3": ProviderMalformedResponseError("bad fixture"),
        }
    )
    result = await ExploreOutgoing(provider).execute("W1")
    assert result.status == "failed"
    assert len(result.nodes) == 2
    assert len(result.edges) == 2
    assert result.unresolved[-1].target == "W3"
    assert result.stop_reasons == ("provider_failure",)


@pytest.mark.asyncio
async def test_cancelled_partial_graph_and_missing_seed() -> None:
    """Cancellation propagates with partial evidence; a missing seed is a failed result."""
    provider = Provider({"W1": paper("W1", "W2"), "W2": asyncio.CancelledError()})
    with pytest.raises(ExplorationCancelled) as error:
        await ExploreOutgoing(provider).execute("W1")
    assert error.value.result.status == "failed"
    assert error.value.result.stop_reasons == ("cancelled",)
    assert len(error.value.result.nodes) == 1
    result = await ExploreOutgoing(provider).execute("W9")
    assert result.seed is None
    assert result.stop_reasons == ("seed_not_found",)


@pytest.mark.asyncio
async def test_merged_reference_keeps_original_assertion() -> None:
    """Merged targets deduplicate while evidence names the original asserted reference."""
    provider = Provider({"W1": paper("W1", "W2", "W3"), "W2": paper("W3")})
    result = await ExploreOutgoing(provider).execute("W1")
    assert provider.calls == ["W1", "W2"]
    assert len(result.nodes) == 2
    assert len(result.edges) == 1
    assert result.edges[0].target == OpenAlexWorkId("W3")
    assert result.edges[0].referenced_id == OpenAlexWorkId("W2")
    assert result.edges[0].evidence.id.endswith(":W2")


@pytest.mark.parametrize(
    "field,value",
    [
        ("depth", 0),
        ("depth", 4),
        ("depth", True),
        ("max_nodes", 0),
        ("max_nodes", 501),
        ("max_edges", 2001),
        ("max_requests", 1001),
        ("max_seconds", float("inf")),
        ("max_seconds", 0),
        ("max_seconds", 121),
    ],
)
def test_invalid_limits(field: str, value: object) -> None:
    """Reject unsupported budgets before any acquisition starts."""
    with pytest.raises(ValueError):
        ExplorationLimits(**{field: value})
