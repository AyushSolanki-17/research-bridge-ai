"""Offline candidate pagination, limits, selection and transport journeys."""

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
from research_bridge.knowledge_graph.application import ExploreOutgoing
from research_bridge.provenance.domain.evidence import Evidence
from research_bridge.research.papers.application import (
    AcquisitionBudget,
    CandidatePage,
    InvalidSearchError,
    ResolvedPaper,
    SearchLimits,
    SearchPapers,
)
from research_bridge.research.papers.application.errors import ProviderTimeoutError
from research_bridge.research.papers.domain.identifiers import Doi, OpenAlexWorkId
from research_bridge.research.papers.domain.paper import Author, Paper, PaperIdentifiers


def record(work: str) -> ResolvedPaper:
    """Build ambiguous synthetic titles with distinct authors and stable evidence."""
    return ResolvedPaper(
        Paper(
            PaperIdentifiers(OpenAlexWorkId(work)),
            title="Shared synthetic title",
            authors=(Author(f"Author {work}"),),
            references_complete=True,
            referenced_works=(OpenAlexWorkId("W3"),) if work == "W2" else (),
        ),
        Evidence.paper_evidence(work, observed_at=datetime(2026, 9, 9, tzinfo=UTC)),
    )


class SearchProvider:
    """Controllable paginated provider with request accounting and lookup support."""

    def __init__(self, pages: list[CandidatePage | BaseException]) -> None:
        self.pages = pages
        self.calls: list[str] = []
        self.lookups: list[str] = []

    async def search_titles(
        self, query: str, *, cursor: str, page_size: int, budget: AcquisitionBudget
    ) -> CandidatePage:
        """Return the cursor-selected page or a configured acquisition failure."""
        budget.consume_request()
        self.calls.append(cursor)
        value = self.pages[0 if cursor == "*" else int(cursor)]
        if isinstance(value, BaseException):
            raise value
        return value

    async def fetch_paper(
        self, identifier: Doi | OpenAlexWorkId, *, budget: AcquisitionBudget | None = None
    ) -> ResolvedPaper:
        """Resolve only the caller's explicit identifier for a graph journey."""
        if budget:
            budget.consume_request()
        self.lookups.append(str(identifier))
        return record(str(identifier))


def test_ambiguous_search_select_explore(capsys: pytest.CaptureFixture[str]) -> None:
    """Each interface lets the caller select the second candidate and trace evidence."""
    provider = SearchProvider([CandidatePage((record("W1"), record("W2")), None)])
    result = asyncio.run(SearchPapers(provider).execute(" Shared   synthetic title "))
    assert result.query == "Shared synthetic title"
    assert provider.lookups == []
    with TestClient(create_app(provider, search_provider=provider)) as client:
        response = client.post("/v1/papers/search", json={"query": result.query})
        assert response.status_code == 200
        assert run(["search", result.query], search_provider=provider) == 0
        assert json.loads(capsys.readouterr().out) == response.json()
        selected = response.json()["candidates"][1]["paper"]["identifiers"]["openalex_id"]["value"]
        graph = asyncio.run(ExploreOutgoing(provider).execute(selected))
        http_graph = client.post("/v1/graphs/outgoing", json={"identifier": selected})
        assert http_graph.status_code == 200
        assert run(["explore", selected], provider=provider) == 0
        cli_graph = json.loads(capsys.readouterr().out)
    assert graph.nodes[0].evidence.id == result.candidates[1].evidence.id
    assert cli_graph["edges"] == http_graph.json()["edges"]
    assert cli_graph["edges"][0]["source"]["value"] == "W2"
    assert cli_graph["edges"][0]["target"]["value"] == "W3"


@pytest.mark.asyncio
async def test_pagination_replays_and_deduplicates() -> None:
    """Repeated records across provider pages never duplicate public candidates."""
    provider = SearchProvider(
        [
            CandidatePage((record("W1"),), "1"),
            CandidatePage((record("W1"),), "2"),
            CandidatePage((record("W2"),), None),
        ]
    )
    search = SearchPapers(provider)
    first = await search.execute("Shared", SearchLimits(page_size=1))
    assert first.status == "more" and first.next_page == 2
    second = await search.execute("Shared", SearchLimits(page_size=1), page=first.next_page)
    assert second.status == "complete" and second.next_page is None
    assert [item.paper.identifiers.openalex_id.value for item in second.candidates] == ["W2"]
    assert second.requests == 3
    past_end = await search.execute("Shared", SearchLimits(page_size=1), page=3)
    assert past_end.candidates == () and past_end.status == "complete"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cursor,status,reason",
    [
        (None, "complete", ()),
        ("*", "truncated", ("repeated_cursor",)),
        ("1", "truncated", ("results",)),
    ],
)
async def test_exact_result_boundary(
    cursor: str | None, status: str, reason: tuple[str, ...]
) -> None:
    """A full allowance is complete only when the provider sequence is exhausted."""
    provider = SearchProvider([CandidatePage((record("W1"),), cursor)])
    result = await SearchPapers(provider).execute("Shared", SearchLimits(max_results=1))
    assert result.status == status and result.stop_reasons == reason
    assert len(result.candidates) == 1


@pytest.mark.asyncio
async def test_no_matches_request_limit_and_partial_failure() -> None:
    """Empty matches are complete; budget and upstream failure preserve partial data."""
    empty = await SearchPapers(SearchProvider([CandidatePage((), None)])).execute("Absent")
    assert empty.status == "complete" and empty.candidates == ()
    provider = SearchProvider(
        [
            CandidatePage((record("W1"),), "1"),
            ProviderTimeoutError("sensitive"),
        ]
    )
    limited = await SearchPapers(provider).execute("Shared", SearchLimits(max_requests=1))
    assert limited.stop_reasons == ("requests",) and limited.requests == 1
    failed = await SearchPapers(provider).execute("Shared")
    assert failed.status == "failed" and failed.stop_reasons == ("provider_failure",)
    assert limited.candidates == failed.candidates == (record("W1"),)


@pytest.mark.asyncio
async def test_controlled_deadline_and_cancellation() -> None:
    """An exact elapsed boundary discards late responses; cancellation stops acquisition."""
    times = iter([0.0, 0.0, 0.0, 30.0])
    provider = SearchProvider([CandidatePage((record("W1"),), None)])
    result = await SearchPapers(provider, clock=lambda: next(times)).execute("Shared")
    assert result.status == "truncated" and result.stop_reasons == ("elapsed_time",)
    assert result.candidates == ()
    cancelled = SearchProvider([asyncio.CancelledError()])
    with pytest.raises(asyncio.CancelledError):
        await SearchPapers(cancelled).execute("Shared")
    assert cancelled.calls == ["*"]


@pytest.mark.parametrize(
    "query,page",
    [("", 1), ("   ", 1), ("x" * 301, 1), ("x|y", 1), ("x,y", 1), ("x", 0), ("x", True), ("x", 11)],
)
def test_invalid_search_before_requests(query: str, page: int) -> None:
    """Invalid query and page inputs fail before provider acquisition."""
    provider = SearchProvider([])
    with pytest.raises(InvalidSearchError):
        asyncio.run(SearchPapers(provider).execute(query, page=page))
    assert provider.calls == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"page_size": True},
        {"page_size": 101},
        {"max_results": 501},
        {"max_requests": 101},
        {"max_seconds": float("nan")},
        {"max_seconds": 121},
    ],
)
def test_search_limit_validation(kwargs: dict) -> None:
    """Every search bound has a validated finite hard maximum."""
    with pytest.raises(ValueError):
        SearchLimits(**kwargs)


@pytest.mark.parametrize(
    "failure,http_status,exit_code", [(None, 200, 5), (ProviderTimeoutError("sensitive"), 502, 4)]
)
def test_partial_search_transports(
    failure: BaseException | None,
    http_status: int,
    exit_code: int,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Partial candidates and safe status agree across HTTP and CLI."""
    provider = SearchProvider(
        [CandidatePage((record("W1"),), "1"), failure or CandidatePage((), None)]
    )
    maximum = 20 if failure else 1
    with TestClient(create_app(search_provider=provider)) as client:
        response = client.post(
            "/v1/papers/search", json={"query": "Shared", "limits": {"max_requests": maximum}}
        )
    assert response.status_code == http_status
    assert "sensitive" not in response.text
    assert (
        run(["search", "Shared", "--max-requests", str(maximum)], search_provider=provider)
        == exit_code
    )
    assert json.loads(capsys.readouterr().out) == response.json()


def test_search_transport_validation(capsys: pytest.CaptureFixture[str]) -> None:
    """HTTP and CLI reject bad queries; explicit selection uses identifier validation."""
    provider = SearchProvider([])
    with TestClient(create_app(provider, search_provider=provider)) as client:
        for body in (
            {"query": " "},
            {"query": "x", "page": True},
            {"query": "x", "limits": {"max_requests": 0}},
            {"query": "x", "unknown": 1},
        ):
            assert client.post("/v1/papers/search", json=body).status_code == 422
        assert (
            client.post("/v1/graphs/outgoing", json={"identifier": "Shared title"}).status_code
            == 422
        )
    assert run(["search", " "], search_provider=provider) == 2
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "invalid_search"
    assert provider.calls == provider.lookups == []


@pytest.mark.asyncio
async def test_adapter_pagination_metadata_and_parameters() -> None:
    """Real adapter encodes title-only queries and preserves metadata and attribution."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.url.params["filter"] == "title.search:Shared & synthetic"
        cursor = request.url.params["cursor"]
        work = "W1" if cursor == "*" else "W2"
        return httpx.Response(
            200,
            json={
                "meta": {"next_cursor": "opaque + / =" if cursor == "*" else None},
                "results": [
                    {
                        "id": f"https://openalex.org/{work}",
                        "title": "Shared",
                        "publication_date": "2020-01-02",
                        "authorships": [{"author": {"display_name": "Author"}}],
                        "primary_location": {"source": {"display_name": "Venue"}},
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await SearchPapers(OpenAlexPaperAdapter(OpenAlexSettings(), client)).execute(
            "Shared & synthetic", SearchLimits(page_size=1), page=2
        )
    assert result.status == "complete" and result.requests == 2
    assert calls[1].url.params["cursor"] == "opaque + / ="
    candidate = result.candidates[0]
    assert str(candidate.paper.publication_date) == "2020-01-02"
    assert candidate.paper.venue.display_name == "Venue"
    assert candidate.paper.authors[0].display_name == "Author"
    assert candidate.evidence.provider_record_id == "W2"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"results": [], "meta": {}},
        {"results": [], "meta": {"next_cursor": 12}},
        {"results": [{}], "meta": {"next_cursor": None}},
        {"results": [None], "meta": {"next_cursor": None}},
    ],
)
async def test_malformed_search_page(payload: dict) -> None:
    """Malformed pages cannot masquerade as a successful empty search."""
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    ) as client:
        result = await SearchPapers(OpenAlexPaperAdapter(OpenAlexSettings(), client)).execute(
            "Shared"
        )
    assert result.status == "failed"


def test_injected_cli_search_ignores_unused_openalex_settings(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An injected search provider needs no unrelated live-provider configuration."""
    monkeypatch.setenv("OPENALEX_TIMEOUT", "invalid")
    provider = SearchProvider([CandidatePage((), None)])
    assert run(["search", "Synthetic"], search_provider=provider) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "complete"


@pytest.mark.asyncio
async def test_stalled_provider_is_cancelled_at_search_deadline() -> None:
    """A blocked page is cancelled while previously acquired candidates survive."""

    class StalledProvider(SearchProvider):
        """Return one page, then block until the application cancels acquisition."""

        async def search_titles(
            self, query: str, *, cursor: str, page_size: int, budget: AcquisitionBudget
        ) -> CandidatePage:
            """Acquire the first page or wait indefinitely on the next cursor."""
            if cursor == "*":
                return await super().search_titles(
                    query, cursor=cursor, page_size=page_size, budget=budget
                )
            budget.consume_request()
            self.calls.append(cursor)
            await asyncio.Event().wait()
            raise AssertionError("Cancelled acquisition must not resume")

    # A controlled timeout context converts only its own cancellation to TimeoutError.
    from unittest.mock import patch

    real_timeout = asyncio.timeout

    def deadline(seconds: float) -> asyncio.Timeout:
        """Expire the blocked page on the next event-loop turn without sleeping."""
        return real_timeout(None if provider.calls == [] else 0)

    provider = StalledProvider([CandidatePage((record("W1"),), "1")])
    with patch("asyncio.timeout", deadline):
        # Fail promptly if the use case loses its deadline guard.
        result = await asyncio.wait_for(SearchPapers(provider).execute("Shared"), timeout=1)
    assert result.status == "truncated"
    assert result.stop_reasons == ("elapsed_time",)
    assert result.candidates == (record("W1"),)
    assert provider.calls == ["*", "1"]
