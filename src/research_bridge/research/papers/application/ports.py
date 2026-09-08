"""Application-owned ports for paper providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from research_bridge.provenance.domain.evidence import Evidence
from research_bridge.research.papers.domain.identifiers import Doi, OpenAlexWorkId
from research_bridge.research.papers.domain.paper import Paper


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
    """Narrow provider port owned by the papers application.

    Implementations live in infrastructure (e.g., ingestion/openalex) and
    must translate provider payloads into canonical domain values without
    leaking provider types.
    """

    async def fetch_paper(self, identifier: Doi | OpenAlexWorkId) -> ResolvedPaper:
        """Fetch a single paper by DOI or OpenAlex work ID.

        Args:
            identifier: Normalized DOI or OpenAlex work identifier.

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
