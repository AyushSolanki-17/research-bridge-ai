"""Tests for ResolvePaper use case with fake provider."""

from datetime import UTC, datetime

import pytest

from research_bridge.provenance.domain.evidence import Evidence
from research_bridge.research.papers.application.errors import PaperNotFoundError
from research_bridge.research.papers.application.ports import ResolvedPaper
from research_bridge.research.papers.application.resolve_paper import ResolvePaper
from research_bridge.research.papers.domain.identifiers import (
    Doi,
    InvalidIdentifierError,
    OpenAlexWorkId,
)
from research_bridge.research.papers.domain.paper import Paper, PaperIdentifiers


class FakeProvider:
    """Fake provider for deterministic use-case tests."""

    def __init__(self, mapping: dict[str, ResolvedPaper] | None = None) -> None:
        self.mapping = mapping or {}
        self.calls: list[str] = []

    async def fetch_paper(self, identifier: Doi | OpenAlexWorkId) -> ResolvedPaper:
        self.calls.append(str(identifier))
        key = str(identifier)
        # Allow lookup by normalized value
        if key in self.mapping:
            return self.mapping[key]
        # Also try Doi vs OpenAlex flexible
        for k, v in self.mapping.items():
            if k.lower() == key.lower():
                return v
        raise PaperNotFoundError(key)


def _fake_paper(work_id: str) -> ResolvedPaper:
    paper = Paper(
        identifiers=PaperIdentifiers(openalex_id=OpenAlexWorkId.parse(work_id)),
        title="Test Paper",
    )
    evidence = Evidence.paper_evidence(work_id, observed_at=datetime.now(UTC))
    return ResolvedPaper(paper=paper, evidence=evidence)


@pytest.mark.asyncio
async def test_resolve_by_doi_and_openalex_without_branching() -> None:
    fake = FakeProvider(
        {
            "10.1234/example": _fake_paper("W1"),
            "W2741809807": _fake_paper("W2741809807"),
        }
    )
    use_case = ResolvePaper(provider=fake)  # type: ignore[arg-type]
    r1 = await use_case.execute("doi:10.1234/example")
    r2 = await use_case.execute("https://openalex.org/W2741809807")
    assert r1.paper.identifiers.openalex_id.value == "W1"
    assert r2.paper.identifiers.openalex_id.value == "W2741809807"
    assert fake.calls == ["10.1234/example", "W2741809807"]


@pytest.mark.asyncio
async def test_resolve_invalid_identifier_raises() -> None:
    fake = FakeProvider()
    use_case = ResolvePaper(provider=fake)  # type: ignore[arg-type]
    with pytest.raises(InvalidIdentifierError):
        await use_case.execute("not-an-id")
    assert fake.calls == []


@pytest.mark.asyncio
async def test_resolve_missing_work_distinguishable() -> None:
    fake = FakeProvider()
    use_case = ResolvePaper(provider=fake)  # type: ignore[arg-type]
    with pytest.raises(PaperNotFoundError):
        await use_case.execute("W9999999999")
