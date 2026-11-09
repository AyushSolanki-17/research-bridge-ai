"""Provider ports consumed by the framework-independent business API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from research_bridge.core.budget import AcquisitionBudget
from research_bridge.core.evidence import Evidence
from research_bridge.core.identifiers import Doi, OpenAlexWorkId
from research_bridge.core.papers import Paper


@dataclass(frozen=True, slots=True)
class ResolvedPaper:
    """Framework-independent result for a resolved paper.

    Attributes:
        paper: Canonical paper record.
        evidence: Stable attribution for the record.
    """

    paper: Paper
    evidence: Evidence


class PaperProviderPort(Protocol):
    """Narrow provider port owned by the business core.

    Implementations live in provider adapters (for example, providers/openalex) and
    must translate provider payloads into canonical domain values without
    leaking provider types.
    """

    async def fetch_paper(
        self, identifier: Doi | OpenAlexWorkId, *, budget: AcquisitionBudget | None = None
    ) -> ResolvedPaper:
        """Fetch a single paper by DOI or OpenAlex work ID.

        Args:
            identifier: Normalized DOI or OpenAlex work identifier.
            budget: Optional operation budget. Implementations must consume a unit
                before every physical request and bound waits by remaining time.

        Returns:
            Canonical paper with stable evidence.

        Raises:
            PaperNotFoundError: If the provider reports the work is missing.
            ProviderRateLimitedError: If the provider reports rate limiting.
            ProviderTimeoutError: If a bounded request times out.
            ProviderMalformedResponseError: If the payload cannot be mapped.
            ProviderRetryExhaustedError: If finite retries are exhausted.
            asyncio.CancelledError: If the caller cancels the operation.
        """
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class CandidatePage:
    """One provider-ordered page of attributed title candidates."""

    candidates: tuple[ResolvedPaper, ...]
    next_cursor: str | None


@runtime_checkable
class PaperSearchPort(Protocol):
    """Acquire title candidates without selecting a paper for the caller."""

    async def search_titles(
        self, query: str, *, cursor: str, page_size: int, budget: AcquisitionBudget
    ) -> CandidatePage:
        """Acquire one bounded page in provider order."""
        ...


@dataclass(frozen=True, slots=True)
class IncomingPage:
    """Attributed citing works and an opaque provider continuation."""

    works: tuple[ResolvedPaper, ...]
    next_cursor: str | None


@runtime_checkable
class IncomingCitationPort(Protocol):
    """Acquire works that explicitly cite a target paper."""

    async def fetch_incoming(
        self, target: OpenAlexWorkId, *, cursor: str, page_size: int, budget: AcquisitionBudget
    ) -> IncomingPage:
        """Acquire one bounded page of citing records."""
        ...
