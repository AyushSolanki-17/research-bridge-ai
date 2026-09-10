"""Resolve a paper by DOI or OpenAlex work identifier."""

from __future__ import annotations

from research_bridge.research.papers.application.ports import PaperProviderPort, ResolvedPaper
from research_bridge.research.papers.domain.identifiers import parse_identifier


class ResolvePaper:
    """Use case to resolve a single paper.

    The injected provider owns acquisition and returns canonical values.
    """

    def __init__(self, provider: PaperProviderPort) -> None:
        """Compose identifier resolution without acquiring data.

        Args:
            provider: Acquisition boundary returning canonical papers and evidence.
        """
        self._provider = provider

    async def execute(self, raw_identifier: str) -> ResolvedPaper:
        """Resolve a paper from any supported identifier form.

        Parsing is deterministic and without paper-specific branches.

        Args:
            raw_identifier: DOI or OpenAlex work identifier in any supported form.

        Returns:
            Canonical paper with stable evidence.

        Raises:
            InvalidIdentifierError: If ``raw_identifier`` is malformed.
            PaperNotFoundError: If the work does not exist.
            ProviderRateLimitedError: On rate limiting.
            ProviderTimeoutError: On timeout.
            ProviderMalformedResponseError: On malformed payload.
            ProviderRetryExhaustedError: On exhausted retries.
            asyncio.CancelledError: If cancelled.
        """
        identifier = parse_identifier(raw_identifier)
        return await self._provider.fetch_paper(identifier)
