"""Direction, pagination, attribution and partial outcomes across all callers."""

import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from research_bridge.api.app import create_app
from research_bridge.cli import run
from research_bridge.ingestion.openalex.infrastructure.openalex_adapter import OpenAlexPaperAdapter
from research_bridge.ingestion.openalex.infrastructure.settings import OpenAlexSettings
from research_bridge.knowledge_graph.application import (
    ExplorationCancelled,
    ExplorationLimits,
    ExplorationMode,
    ExploreCitations,
    IncomingPage,
)
from research_bridge.provenance.domain.evidence import Evidence
from research_bridge.research.papers.application import AcquisitionBudget, ResolvedPaper
from research_bridge.research.papers.application.errors import ProviderMalformedResponseError
from research_bridge.research.papers.domain.identifiers import Doi, OpenAlexWorkId
from research_bridge.research.papers.domain.paper import Paper, PaperIdentifiers


def record(work: str, *references: str, complete: bool = True) -> ResolvedPaper:
    """Create a canonical fixture with explicit citation assertions."""
    return ResolvedPaper(
        Paper(
            PaperIdentifiers(OpenAlexWorkId(work)),
            title=work,
            referenced_works=tuple(OpenAlexWorkId(ref) for ref in references),
            references_complete=complete,
        ),
        Evidence.paper_evidence(work, observed_at=datetime(2026, 9, 10, tzinfo=UTC)),
    )


class CitationProvider:
    """One-record pages make every incoming continuation and request observable."""

    def __init__(
        self, records: list[ResolvedPaper], *, failure: BaseException | None = None
    ) -> None:
        """Configure the synthetic corpus and optional second-page failure."""
        self.records = {item.paper.identifiers.openalex_id: item for item in records}
        self.calls = []
        self.failure = failure

    async def fetch_paper(
        self, identifier: Doi | OpenAlexWorkId, *, budget: AcquisitionBudget | None = None
    ) -> ResolvedPaper:
        """Acquire one singleton and charge the shared request budget."""
        assert budget is not None
        budget.consume_request()
        self.calls.append(("lookup", str(identifier)))
        return self.records[identifier]

    async def fetch_incoming(
        self, target: OpenAlexWorkId, *, cursor: str, page_size: int, budget: AcquisitionBudget
    ) -> IncomingPage:
        """Return provider-backed incoming records, including optional failures."""
        budget.consume_request()
        self.calls.append(("incoming", target.value, cursor))
        if cursor != "*" and self.failure:
            raise self.failure
        works = [item for item in self.records.values() if target in item.paper.referenced_works]
        offset = 0 if cursor == "*" else int(cursor)
        end = offset + 1
        return IncomingPage(tuple(works[offset:end]), str(end) if end < len(works) else None)


def corpus() -> list[ResolvedPaper]:
    """Return asymmetric incoming and outgoing chains with a cycle at depth three."""
    return [
        record("W1", "W2"),
        record("W2", "W3"),
        record("W3", "W4"),
        record("W4"),
        record("W5", "W1"),
        record("W6", "W5"),
        record("W7", "W6", "W1"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["incoming", "outgoing", "both"])
@pytest.mark.parametrize("depth", [1, 2, 3])
async def test_all_modes_and_depths(mode: ExplorationMode, depth: int) -> None:
    """Follow the chosen direction at every hop without reversing citation facts."""
    provider = CitationProvider(corpus())
    result = await ExploreCitations(provider).execute(
        "W1", ExplorationLimits(depth=depth), mode=mode
    )
    expected = {"W1"}
    frontier = {"W1"}
    assertions = {
        (str(p.paper.identifiers.openalex_id), str(r))
        for p in corpus()
        for r in p.paper.referenced_works
    }
    expected_edges = set()
    for _ in range(depth):
        next_frontier = set()
        for source, target in assertions:
            if (mode != "incoming" and source in frontier) or (
                mode != "outgoing" and target in frontier
            ):
                expected_edges.add((source, target))
                next_frontier.update((source, target))
        frontier = next_frontier - expected
        expected.update(next_frontier)
    assert result.status == "complete"
    assert result.mode == mode
    assert {str(p.paper.identifiers.openalex_id) for p in result.nodes} == expected
    assert {(str(e.source), str(e.target)) for e in result.edges} == expected_edges
    assert len(result.edges) == len(expected_edges)
    for edge in result.edges:
        assert edge.evidence.id == f"openalex:citation:{edge.source}:{edge.target}"
        assert edge.evidence.source_url == f"https://openalex.org/{edge.source}"
        assert edge.evidence.observed_at == provider.records[edge.source].evidence.observed_at


@pytest.mark.asyncio
async def test_combined_request_limit_and_partial_page_failure() -> None:
    """Both directions share accounting and retain successful incoming pages."""
    provider = CitationProvider(corpus())
    result = await ExploreCitations(provider).execute(
        "W1", ExplorationLimits(max_requests=3), mode="both"
    )
    assert result.status == "truncated"
    assert result.stop_reasons == ("requests",)
    assert result.requests == 3
    assert result.unread_incoming_pages[0].cursor == "1"
    assert result.unread_incoming_pages[0].target == OpenAlexWorkId("W1")
    assert result.unread_incoming_pages[0].reason == "requests"
    assert [(str(e.source), str(e.target)) for e in result.edges] == [("W1", "W2"), ("W5", "W1")]
    assert provider.calls == [("lookup", "W1"), ("lookup", "W2"), ("incoming", "W1", "*")]
    provider = CitationProvider(corpus(), failure=ProviderMalformedResponseError("bad page"))
    failed = await ExploreCitations(provider).execute("W1", mode="incoming")
    assert failed.status == "failed"
    assert failed.stop_reasons == ("provider_failure",)
    assert len(failed.edges) == 1
    assert failed.unread_incoming_pages[0].reason == "provider_failure"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["incoming", "both"])
async def test_directed_cycles_expand_each_work_once(mode: ExplorationMode) -> None:
    """A directed cycle and self-citation retain edges without reacquiring neighborhoods."""
    provider = CitationProvider([record("W1", "W2", "W1"), record("W2", "W1")])
    result = await ExploreCitations(provider).execute("W1", ExplorationLimits(depth=3), mode=mode)
    assert result.status == "complete"
    assert len(result.nodes) == 2
    assert {(str(e.source), str(e.target)) for e in result.edges} == {
        ("W1", "W1"),
        ("W1", "W2"),
        ("W2", "W1"),
    }
    starts = [call[1] for call in provider.calls if call[0] == "incoming" and call[2] == "*"]
    assert starts == ["W1", "W2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("limit,reason", [("max_nodes", "nodes"), ("max_edges", "edges")])
async def test_exact_count_boundaries(limit: str, reason: str) -> None:
    """A full bound is complete only when no additional unique data remains."""
    bounds = ExplorationLimits(**{limit: 2 if limit == "max_nodes" else 1})
    complete = await ExploreCitations(CitationProvider([record("W1"), record("W2", "W1")])).execute(
        "W1", bounds, mode="incoming"
    )
    assert complete.status == "complete"
    truncated = await ExploreCitations(CitationProvider(corpus())).execute(
        "W1", bounds, mode="incoming"
    )
    assert truncated.status == "truncated"
    assert truncated.stop_reasons == (reason,)
    assert len(truncated.edges) == 1


@pytest.mark.asyncio
async def test_incomplete_outgoing_metadata_does_not_invalidate_incoming_scope() -> None:
    """An incoming-only query can complete even if the seed's references are missing."""
    result = await ExploreCitations(CitationProvider([record("W1", complete=False)])).execute(
        "W1", mode="incoming"
    )
    assert result.status == "complete"
    assert "referenced_works" in result.incomplete_metadata[0].fields


@pytest.mark.asyncio
async def test_repeated_cursor_and_duplicate_records() -> None:
    """Repeated pagination stops with deduplicated evidence and truthful truncation."""

    class Repeated(CitationProvider):
        """Return the same record and cursor repeatedly."""

        async def fetch_incoming(
            self, target: OpenAlexWorkId, *, cursor: str, page_size: int, budget: AcquisitionBudget
        ) -> IncomingPage:
            """Charge each page even when it adds no new records."""
            budget.consume_request()
            return IncomingPage((record("W2", "W1"), record("W2", "W1")), "again")

    result = await ExploreCitations(Repeated([record("W1")])).execute("W1", mode="incoming")
    assert result.status == "truncated"
    assert result.stop_reasons == ("repeated_cursor",)
    assert len(result.edges) == 1
    assert result.requests == 3


@pytest.mark.asyncio
async def test_reject_unsupported_incoming_assertion() -> None:
    """A filtered result without the explicit reference cannot create an edge."""

    class Unsupported(CitationProvider):
        """Supply a contradictory provider page."""

        async def fetch_incoming(
            self, target: OpenAlexWorkId, *, cursor: str, page_size: int, budget: AcquisitionBudget
        ) -> IncomingPage:
            """Return a work citing a different target."""
            budget.consume_request()
            return IncomingPage((record("W2", "W3"),), None)

    result = await ExploreCitations(Unsupported([record("W1")])).execute("W1", mode="incoming")
    assert result.status == "failed"
    assert not result.edges


@pytest.mark.asyncio
async def test_cancellation_retains_prior_page() -> None:
    """Cancellation stops further acquisition and carries the graph already acquired."""
    provider = CitationProvider(corpus(), failure=asyncio.CancelledError())
    with pytest.raises(ExplorationCancelled) as caught:
        await ExploreCitations(provider).execute("W1", mode="incoming")
    assert caught.value.result.status == "failed"
    assert caught.value.result.stop_reasons == ("cancelled",)
    assert len(caught.value.result.edges) == 1
    assert len(provider.calls) == 3


@pytest.mark.asyncio
async def test_controlled_elapsed_boundary() -> None:
    """A page arriving exactly at the deadline is excluded from the partial graph."""
    now = [0.0]

    class Slow(CitationProvider):
        """Advance the injected clock during incoming acquisition."""

        async def fetch_incoming(
            self, target: OpenAlexWorkId, *, cursor: str, page_size: int, budget: AcquisitionBudget
        ) -> IncomingPage:
            """Make the page arrive exactly at the shared deadline."""
            page = await super().fetch_incoming(
                target, cursor=cursor, page_size=page_size, budget=budget
            )
            now[0] = 1.0
            return page

    result = await ExploreCitations(Slow(corpus()), clock=lambda: now[0]).execute(
        "W1", ExplorationLimits(max_seconds=1), mode="incoming"
    )
    assert result.stop_reasons == ("elapsed_time",)
    assert not result.edges


@pytest.mark.parametrize("mode", ["outgoing", "incoming", "both"])
@pytest.mark.parametrize("max_requests,status", [(20, "complete"), (1, "truncated")])
def test_http_cli_mode_journey(
    mode: ExplorationMode, max_requests: int, status: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Transports preserve the library's directed edges, limits and completion status."""
    bounds = ExplorationLimits(max_requests=max_requests)
    library = asyncio.run(
        ExploreCitations(CitationProvider(corpus())).execute("W1", bounds, mode=mode)
    )
    with TestClient(create_app(CitationProvider(corpus()))) as client:
        response = client.post(
            "/v1/graphs/explore",
            json={"identifier": "W1", "mode": mode, "limits": {"max_requests": max_requests}},
        )
    exit_code = run(
        ["explore", "W1", "--mode", mode, "--max-requests", str(max_requests)],
        provider=CitationProvider(corpus()),
    )
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200
    assert exit_code == (5 if status == "truncated" else 0)
    for result in (cli, response.json()):
        assert result["mode"] == mode
        assert result["status"] == status == library.status
        assert result["requests"] == library.requests
        assert [(e["source"]["value"], e["target"]["value"]) for e in result["edges"]] == [
            (str(e.source), str(e.target)) for e in library.edges
        ]
        assert [e["evidence"]["id"] for e in result["edges"]] == [
            e.evidence.id for e in library.edges
        ]


def test_transport_validation_and_partial_failure(capsys: pytest.CaptureFixture[str]) -> None:
    """Reject invalid modes and preserve prior pages in HTTP and CLI failure results."""
    provider = CitationProvider(corpus(), failure=ProviderMalformedResponseError("bad page"))
    with TestClient(create_app(provider)) as client:
        assert (
            client.post(
                "/v1/graphs/explore", json={"identifier": "W1", "mode": "wrong"}
            ).status_code
            == 422
        )
        failed = client.post("/v1/graphs/explore", json={"identifier": "W1", "mode": "incoming"})
        assert failed.status_code == 502
        assert len(failed.json()["edges"]) == 1
        assert (
            client.post(
                "/v1/graphs/outgoing", json={"identifier": "W1", "mode": "both"}
            ).status_code
            == 422
        )
    assert run(["explore", "W1", "--mode", "incoming"], provider=provider) == 4
    assert len(json.loads(capsys.readouterr().out)["edges"]) == 1


@pytest.mark.asyncio
async def test_openalex_filter_pagination_and_retry_accounting() -> None:
    """The adapter acquires citing works through the official filter and opaque cursors."""
    calls = []

    def respond(request: httpx.Request) -> httpx.Response:
        """Serve two pages, with a transient failure before the first succeeds."""
        calls.append(request)
        assert request.url.params["filter"] == "cites:W1"
        assert request.url.params["per_page"] == "100"
        assert request.headers["Authorization"] == "Bearer synthetic-key"
        assert "api_key" not in request.url.params
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        cursor = request.url.params["cursor"]
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "https://openalex.org/W2",
                        "referenced_works": ["https://openalex.org/W1"],
                    }
                ]
                if cursor == "*"
                else [],
                "meta": {"next_cursor": "opaque+/=" if cursor == "*" else None},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        adapter = OpenAlexPaperAdapter(OpenAlexSettings(api_key="synthetic-key"), client)
        result = await ExploreCitations(adapter).execute(record("W1"), mode="incoming")
        assert not client.is_closed
    assert result.status == "complete"
    assert result.requests == 3
    assert calls[-1].url.params["cursor"] == "opaque+/="
    assert result.edges[0].evidence.id == "openalex:citation:W2:W1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"results": [], "meta": {}},
        {"results": [], "meta": {"next_cursor": ""}},
        {"results": [{"id": "invalid"}], "meta": {"next_cursor": None}},
    ],
)
async def test_malformed_incoming_pages(payload: dict[str, object]) -> None:
    """Invalid provider pages fail without fabricating graph completeness."""
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    ) as client:
        adapter = OpenAlexPaperAdapter(client=client)
        with pytest.raises(ProviderMalformedResponseError):
            await adapter.fetch_incoming(
                OpenAlexWorkId("W1"), cursor="*", page_size=100, budget=AcquisitionBudget(3, 10)
            )
