"""Distinguish invalid provider metadata from unexpected translation defects."""

from typing import NoReturn

import httpx
import pytest

from research_bridge.ingestion.openalex.infrastructure import translation
from research_bridge.ingestion.openalex.infrastructure.openalex_adapter import OpenAlexPaperAdapter
from research_bridge.ingestion.openalex.infrastructure.settings import OpenAlexSettings
from research_bridge.research.papers.application import AcquisitionBudget, ResolvedPaper
from research_bridge.research.papers.application.errors import ProviderMalformedResponseError
from research_bridge.research.papers.domain.identifiers import Doi, OpenAlexWorkId


async def _fetch_record(operation: str, work: dict[str, object]) -> ResolvedPaper:
    """Acquire one synthetic work through a public adapter operation.

    Args:
        operation: Lookup, title search or incoming citation acquisition.
        work: Provider work payload to return through the mock HTTP transport.

    Returns:
        The translated record from the selected operation.

    Raises:
        Exception: Propagates acquisition or translation errors to the test.
    """
    payload = work if operation == "lookup" else {"results": [work], "meta": {"next_cursor": None}}
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    ) as client:
        adapter = OpenAlexPaperAdapter(OpenAlexSettings(max_retries=0), client)
        if operation == "lookup":
            return await adapter.fetch_paper(OpenAlexWorkId("W1"))
        if operation == "search":
            page = await adapter.search_titles(
                "Synthetic", cursor="*", page_size=1, budget=AcquisitionBudget(1, 30)
            )
            return page.candidates[0]
        incoming = await adapter.fetch_incoming(
            OpenAlexWorkId("W1"), cursor="*", page_size=1, budget=AcquisitionBudget(1, 30)
        )
        return incoming.works[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["lookup", "search", "incoming"])
@pytest.mark.parametrize("work", [{}, {"id": "invalid"}])
async def test_invalid_required_identity_is_provider_error(
    operation: str, work: dict[str, object]
) -> None:
    """All acquisition paths classify missing or invalid work IDs as provider errors.

    Args:
        operation: Public acquisition operation under test.
        work: Payload with a missing or invalid required identity.
    """
    with pytest.raises(ProviderMalformedResponseError):
        await _fetch_record(operation, work)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["lookup", "search", "incoming"])
@pytest.mark.parametrize("fallback_doi", ["invalid", "10.1234/fallback"])
async def test_invalid_optional_identifiers_preserve_available_metadata(
    operation: str, fallback_doi: str
) -> None:
    """Invalid DOI/reference values retain valid fallback data and explicit gaps.

    Args:
        operation: Public acquisition operation under test.
        fallback_doi: Valid or invalid secondary DOI reported by the provider.
    """
    record = await _fetch_record(
        operation,
        {
            "id": "W1",
            "title": "Synthetic",
            "doi": "invalid",
            "ids": {"doi": fallback_doi},
            "referenced_works": ["invalid", "W2"],
        },
    )
    assert record.paper.title == "Synthetic"
    assert record.paper.identifiers.doi == (
        Doi("10.1234/fallback") if fallback_doi != "invalid" else None
    )
    assert record.paper.referenced_works == (OpenAlexWorkId("W2"),)
    assert not record.paper.references_complete
    assert record.evidence.provider_record_id == "W1"


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["lookup", "search", "incoming"])
@pytest.mark.parametrize("field", ["id", "doi", "ids", "referenced_works", "abstract"])
async def test_unexpected_translation_defect_propagates(
    operation: str, field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Programming defects must neither become provider errors nor missing metadata.

    Args:
        operation: Public acquisition operation under test.
        field: Translation location at which to inject the unexpected failure.
        monkeypatch: Fixture that restores the parser after fault injection.
    """
    defect = RuntimeError("synthetic translation defect")
    work: dict[str, object] = {"id": "W1"}
    if field == "abstract":

        def broken_abstract(value: object) -> NoReturn:
            raise defect

        monkeypatch.setattr(translation, "reconstruct_abstract", broken_abstract)
    else:
        parser = Doi if field in ("doi", "ids") else OpenAlexWorkId
        original_parse = parser.parse

        def broken_parse(raw: str) -> Doi | OpenAlexWorkId:
            if raw == "broken":
                raise defect
            return original_parse(raw)

        monkeypatch.setattr(parser, "parse", staticmethod(broken_parse))
        if field == "ids":
            work[field] = {"doi": "broken"}
        elif field == "referenced_works":
            work[field] = ["broken"]
        else:
            work[field] = "broken"
    with pytest.raises(RuntimeError) as raised:
        await _fetch_record(operation, work)
    assert raised.value is defect
