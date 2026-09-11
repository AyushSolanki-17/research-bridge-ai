"""Application-owned acquisition contract for incoming citation pages."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from research_bridge.research.papers.application import AcquisitionBudget, ResolvedPaper
from research_bridge.research.papers.domain.identifiers import OpenAlexWorkId


@dataclass(frozen=True)
class IncomingPage:
    """Attributed citing works and an opaque continuation.

    Attributes:
        works: Records whose reference lists explicitly support the queried citation.
        next_cursor: Next provider page, or None when acquisition is exhausted.
    """

    works: tuple[ResolvedPaper, ...]
    next_cursor: str | None


@runtime_checkable
class IncomingCitationPort(Protocol):
    """Provider boundary for incoming citations, independent of singleton lookup."""

    async def fetch_incoming(
        self, target: OpenAlexWorkId, *, cursor: str, page_size: int, budget: AcquisitionBudget
    ) -> IncomingPage:
        """Acquire citing records with explicit reference assertions.

        Args:
            target: Referenced work whose incoming neighborhood is requested.
            cursor: Opaque continuation; '*' begins acquisition.
            page_size: Maximum records in a page, from 1 through 100.
            budget: Shared allowance; count every request, redirect and retry.

        Returns:
            Canonical citing records and continuation, in stable provider order.

        Raises:
            ProviderMalformedResponseError: If records or pagination are invalid.
            AcquisitionLimitReached: If request or elapsed allowance is exhausted.
            asyncio.CancelledError: If acquisition is cancelled.
        """
        ...
