"""Deterministic adapter tests for OpenAlex singleton resolution."""

import asyncio
from datetime import date

import httpx
import pytest

from research_bridge.ingestion.openalex.infrastructure.openalex_adapter import (
    OpenAlexPaperAdapter,
    reconstruct_abstract,
)
from research_bridge.ingestion.openalex.infrastructure.settings import OpenAlexSettings
from research_bridge.research.papers.application.errors import (
    PaperNotFoundError,
    ProviderMalformedResponseError,
    ProviderRateLimitedError,
    ProviderRetryExhaustedError,
    ProviderTimeoutError,
)
from research_bridge.research.papers.domain.identifiers import Doi, OpenAlexWorkId


def _complete_payload(work_id: str = "W2741809807") -> dict:
    return {
        "id": f"https://openalex.org/{work_id}",
        "doi": "https://doi.org/10.7717/peerj-cs.214",
        "ids": {
            "doi": "https://doi.org/10.7717/peerj-cs.214",
            "openalex": f"https://openalex.org/{work_id}",
        },
        "title": "Attention Is All You Need",
        "display_name": "Attention Is All You Need",
        "publication_date": "2017-12-06",
        "primary_location": {
            "source": {
                "display_name": "Advances in Neural Information Processing Systems",
                "id": "S123",
            }
        },
        "authorships": [
            {
                "author": {
                    "display_name": "Vaswani",
                    "orcid": "https://orcid.org/0000-0001-0000-0001",
                },
                "author_position": "first",
            },
            {"author": {"display_name": "Shazeer"}, "author_position": "middle"},
        ],
        "abstract_inverted_index": {
            "Attention": [0],
            "is": [1],
            "all": [2],
            "you": [3],
            "need": [4],
        },
        "cited_by_count": 50000,
        "topics": [
            {
                "id": "https://openalex.org/T123",
                "display_name": "Natural Language Processing",
                "score": 0.97,
                "subfield": {"display_name": "Linguistics"},
                "field": {"display_name": "Computer Science"},
                "domain": {"display_name": "Physical Sciences"},
            }
        ],
        "referenced_works": ["https://openalex.org/W111", "https://openalex.org/W222"],
    }


def _second_paper_payload() -> dict:
    return {
        "id": "https://openalex.org/W2122039852",
        "doi": "https://doi.org/10.1038/nature14539",
        "title": "Deep Residual Learning for Image Recognition",
        "display_name": "Deep Residual Learning for Image Recognition",
        "publication_date": "2015-12-10",
        "primary_location": {"source": {"display_name": "CVPR", "id": "S456"}},
        "authorships": [{"author": {"display_name": "He"}, "author_position": "first"}],
        "abstract_inverted_index": {"Deep": [0], "Residual": [1]},
        "cited_by_count": 0,
        "topics": [],
        "referenced_works": [],
    }


def _sparse_payload() -> dict:
    return {
        "id": "https://openalex.org/W9999999999",
        # missing doi, title, publication_date, venue, authors, abstract, topics
        "authorships": [],
        # no cited_by_count key -> should be None
        # abstract_inverted_index missing
        # topics missing
    }


@pytest.mark.asyncio
async def test_successful_resolution_two_seeds() -> None:
    complete = _complete_payload("W2741809807")
    second = _second_paper_payload()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "W2741809807" in url or "10.7717" in url:
            return httpx.Response(200, json=complete)
        if "W2122039852" in url:
            return httpx.Response(200, json=second)
        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
        settings = OpenAlexSettings(
            base_url="https://api.openalex.org", max_retries=0, timeout_seconds=5
        )
        adapter = OpenAlexPaperAdapter(settings=settings, client=client)

        res1 = await adapter.fetch_paper(OpenAlexWorkId.parse("W2741809807"))
        assert res1.paper.identifiers.openalex_id.value == "W2741809807"
        assert res1.paper.title == "Attention Is All You Need"
        assert res1.paper.publication_date == date(2017, 12, 6)
        assert res1.paper.abstract == "Attention is all you need"
        assert res1.paper.cited_by_count == 50000
        assert len(res1.paper.authors) == 2
        assert (
            res1.paper.venue
            and res1.paper.venue.display_name == "Advances in Neural Information Processing Systems"
        )
        assert len(res1.paper.topics) == 1
        assert res1.paper.topics[0].score == 0.97
        assert res1.paper.topics[0].inference_status.value == "inferred_provider"
        assert res1.evidence.id == "openalex:work:W2741809807"

        res2 = await adapter.fetch_paper(OpenAlexWorkId.parse("W2122039852"))
        assert res2.paper.identifiers.openalex_id.value == "W2122039852"
        assert res2.paper.cited_by_count == 0  # zero preserved
        assert res2.paper.abstract == "Deep Residual"


@pytest.mark.asyncio
async def test_sparse_metadata_preserved_as_none() -> None:
    payload = _sparse_payload()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = OpenAlexSettings(base_url="https://api.openalex.org", max_retries=0)
        adapter = OpenAlexPaperAdapter(settings=settings, client=client)
        res = await adapter.fetch_paper(OpenAlexWorkId.parse("W9999999999"))
        assert res.paper.title is None
        assert res.paper.publication_date is None
        assert res.paper.venue is None
        assert res.paper.abstract is None
        assert res.paper.cited_by_count is None
        assert res.paper.authors == ()
        assert res.paper.topics == ()


@pytest.mark.asyncio
async def test_malformed_payload_raises() -> None:
    malformed = {"doi": "https://doi.org/10.1234/abc"}  # missing id

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=malformed)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = OpenAlexSettings(base_url="https://api.openalex.org", max_retries=0)
        adapter = OpenAlexPaperAdapter(settings=settings, client=client)
        with pytest.raises(ProviderMalformedResponseError):
            await adapter.fetch_paper(OpenAlexWorkId.parse("W123"))


def test_abstract_reconstruction_variants() -> None:
    assert reconstruct_abstract({"hello": [0], "world": [1]}) == "hello world"
    assert reconstruct_abstract(None) is None
    assert reconstruct_abstract({}) is None
    assert reconstruct_abstract("not-a-dict") is None  # type: ignore[arg-type]
    assert reconstruct_abstract({"a": [0, 0]}) is None  # duplicate position malformed
    assert reconstruct_abstract({"a": "not-a-list"}) is None  # type: ignore[dict-item]
    # Unordered positions still reconstructed correctly
    assert reconstruct_abstract({"world": [1], "hello": [0]}) == "hello world"


@pytest.mark.asyncio
async def test_zero_vs_missing_citation_counts() -> None:
    zero_payload = {**_complete_payload("W1"), "cited_by_count": 0, "id": "https://openalex.org/W1"}
    missing_payload = {k: v for k, v in _complete_payload("W2").items() if k != "cited_by_count"}
    missing_payload["id"] = "https://openalex.org/W2"

    def handler(request: httpx.Request) -> httpx.Response:
        if "W1" in str(request.url):
            return httpx.Response(200, json=zero_payload)
        return httpx.Response(200, json=missing_payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = OpenAlexSettings(base_url="https://api.openalex.org", max_retries=0)
        adapter = OpenAlexPaperAdapter(settings=settings, client=client)
        r1 = await adapter.fetch_paper(OpenAlexWorkId.parse("W1"))
        r2 = await adapter.fetch_paper(OpenAlexWorkId.parse("W2"))
        assert r1.paper.cited_by_count == 0
        assert r2.paper.cited_by_count is None


@pytest.mark.asyncio
async def test_redirect_uses_canonical_id() -> None:
    # Request old id W999, payload returns canonical W111
    canonical = _complete_payload("W111")

    def handler(request: httpx.Request) -> httpx.Response:
        # Simulate redirect by returning canonical payload regardless of requested id
        return httpx.Response(200, json=canonical)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = OpenAlexSettings(base_url="https://api.openalex.org", max_retries=0)
        adapter = OpenAlexPaperAdapter(settings=settings, client=client)
        res = await adapter.fetch_paper(OpenAlexWorkId.parse("W999"))
        # Evidence and paper must reflect canonical id from payload, not requested
        assert res.paper.identifiers.openalex_id.value == "W111"
        assert res.evidence.id == "openalex:work:W111"
        assert res.evidence.provider_record_id == "W111"


@pytest.mark.asyncio
async def test_missing_work_404() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = OpenAlexSettings(base_url="https://api.openalex.org", max_retries=0)
        adapter = OpenAlexPaperAdapter(settings=settings, client=client)
        with pytest.raises(PaperNotFoundError):
            await adapter.fetch_paper(OpenAlexWorkId.parse("W404"))


@pytest.mark.asyncio
async def test_rate_limited() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = OpenAlexSettings(base_url="https://api.openalex.org", max_retries=0)
        adapter = OpenAlexPaperAdapter(settings=settings, client=client)
        with pytest.raises(ProviderRateLimitedError):
            await adapter.fetch_paper(OpenAlexWorkId.parse("W1"))


@pytest.mark.asyncio
async def test_timeout() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(
            "timeout", request=httpx.Request("GET", "https://api.openalex.org/works/W1")
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = OpenAlexSettings(
            base_url="https://api.openalex.org", max_retries=0, timeout_seconds=0.01
        )
        adapter = OpenAlexPaperAdapter(settings=settings, client=client)
        with pytest.raises(ProviderTimeoutError):
            await adapter.fetch_paper(OpenAlexWorkId.parse("W1"))


@pytest.mark.asyncio
async def test_retry_exhausted_after_transient() -> None:
    count = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        count["n"] += 1
        return httpx.Response(500, json={"error": "server error"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = OpenAlexSettings(
            base_url="https://api.openalex.org", max_retries=2, timeout_seconds=5
        )
        adapter = OpenAlexPaperAdapter(settings=settings, client=client)
        with pytest.raises(ProviderRetryExhaustedError) as excinfo:
            await adapter.fetch_paper(OpenAlexWorkId.parse("W1"))
        assert excinfo.value.attempts == 3
        assert count["n"] == 3


@pytest.mark.asyncio
async def test_cancellation_propagates() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        # Simulate cancellation during request
        raise asyncio.CancelledError()

    # Use a transport that raises CancelledError via custom client mock
    class CancellingClient:
        async def get(self, *_, **__) -> httpx.Response:
            raise asyncio.CancelledError()

        async def aclose(self) -> None:
            return None

    settings = OpenAlexSettings(base_url="https://api.openalex.org", max_retries=2)
    adapter = OpenAlexPaperAdapter(settings=settings, client=CancellingClient())  # type: ignore[arg-type]
    with pytest.raises(asyncio.CancelledError):
        await adapter.fetch_paper(OpenAlexWorkId.parse("W1"))


@pytest.mark.asyncio
async def test_malformed_json_raises() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = OpenAlexSettings(base_url="https://api.openalex.org", max_retries=0)
        adapter = OpenAlexPaperAdapter(settings=settings, client=client)
        with pytest.raises(ProviderMalformedResponseError):
            await adapter.fetch_paper(OpenAlexWorkId.parse("W1"))


@pytest.mark.asyncio
async def test_doi_lookup_uses_doi_url() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=_complete_payload("W2741809807"))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = OpenAlexSettings(base_url="https://api.openalex.org", max_retries=0)
        adapter = OpenAlexPaperAdapter(settings=settings, client=client)
        await adapter.fetch_paper(Doi.parse("10.7717/peerj-cs.214"))
        assert "https://doi.org/10.7717/peerj-cs.214" in captured["url"]


def test_topic_score_not_zero_when_missing() -> None:
    payload = _complete_payload("W1")
    payload["topics"] = [{"id": "T1", "display_name": "Topic", "score": None}]
    # Direct translation via adapter's internal? Test via full fetch
    # Instead test parsing directly: missing score stays None, not 0.
    # Use adapter via mock
    import asyncio

    async def run() -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=payload)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            settings = OpenAlexSettings(base_url="https://api.openalex.org", max_retries=0)
            adapter = OpenAlexPaperAdapter(settings=settings, client=client)
            res = await adapter.fetch_paper(OpenAlexWorkId.parse("W1"))
            assert res.paper.topics[0].score is None
            assert res.paper.topics[0].inference_status.value == "inferred_provider"

    asyncio.run(run())
