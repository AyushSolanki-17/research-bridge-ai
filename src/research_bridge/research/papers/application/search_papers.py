"""Bounded title candidate search with explicit caller selection."""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from research_bridge.research.papers.application.acquisition import (
    AcquisitionBudget,
    AcquisitionLimitReached,
)
from research_bridge.research.papers.application.errors import (
    PaperNotFoundError,
    ProviderMalformedResponseError,
    ProviderRateLimitedError,
    ProviderRetryExhaustedError,
    ProviderTimeoutError,
)
from research_bridge.research.papers.application.ports import ResolvedPaper


class InvalidSearchError(ValueError):
    """The title query or requested candidate page is invalid."""


@dataclass(frozen=True, slots=True)
class SearchLimits:
    """Validated search bounds, including replay of earlier candidate pages.

    Attributes:
        page_size: Candidates per public page, from 1 to 100.
        max_results: Unique candidates considered per search, from 1 to 500.
        max_requests: Physical requests per call, from 1 to 100.
        max_seconds: Finite elapsed allowance per call, greater than 0 up to 120.
    """

    page_size: int = 10
    max_results: int = 100
    max_requests: int = 20
    max_seconds: float = 30.0

    def __post_init__(self) -> None:
        for name, maximum in (("page_size", 100), ("max_results", 500), ("max_requests", 100)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f"{name} must be an integer from 1 to {maximum}")
        if (
            isinstance(self.max_seconds, bool)
            or not math.isfinite(self.max_seconds)
            or not 0 < self.max_seconds <= 120
        ):
            raise ValueError("max_seconds must be finite and greater than 0, up to 120")


@dataclass(frozen=True, slots=True)
class CandidatePage:
    """Canonical provider page; a null cursor means the provider sequence ended.

    Attributes:
        candidates: Attributed works in provider order.
        next_cursor: Opaque continuation value, or None at the end.
    """

    candidates: tuple[ResolvedPaper, ...]
    next_cursor: str | None


class PaperSearchPort(Protocol):
    """Acquisition boundary for title-only candidate pages."""

    async def search_titles(
        self, query: str, *, cursor: str, page_size: int, budget: AcquisitionBudget
    ) -> CandidatePage:
        """Acquire one page, accounting for every physical request and wait.

        Args:
            query: Validated title text.
            cursor: Opaque provider cursor; '*' starts a sequence.
            page_size: Maximum number of records requested.
            budget: Shared limits for the complete search call.

        Returns:
            Canonical attributed candidates and continuation.

        Raises:
            AcquisitionLimitReached: When the shared allowance is exhausted.
            ProviderMalformedResponseError: When the response cannot be translated.
            ProviderRateLimitedError: When rate limiting prevents acquisition.
            ProviderTimeoutError: When a bounded request times out.
            ProviderRetryExhaustedError: When finite retries fail.
            asyncio.CancelledError: When cancelled; no further requests may start.
        """
        ...


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One deduplicated candidate page and truthful acquisition status.

    Attributes:
        query: Normalized title query; no candidate is implicitly selected.
        page: One-based requested page.
        candidates: Available candidates on this page, each with evidence.
        next_page: Next page only when more provider results can be reviewed.
        status: Complete at provider end, more for pagination, truncated at a
            limit or repeated cursor, or failed on an upstream error.
        stop_reasons: Machine-readable reasons for incomplete acquisition.
        limits: Applied bounds, including replay of prior pages.
        requests: Physical requests consumed by this call.
    """

    query: str
    page: int
    candidates: tuple[ResolvedPaper, ...]
    next_page: int | None
    status: Literal["complete", "more", "truncated", "failed"]
    stop_reasons: tuple[str, ...]
    limits: SearchLimits
    requests: int


class SearchPapers:
    """Review title candidates through an injected provider without selecting a seed."""

    def __init__(
        self, provider: PaperSearchPort, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        """Compose acquisition and an optionally controlled monotonic clock."""
        self._provider = provider
        self._clock = clock

    async def execute(
        self, query: str, limits: SearchLimits | None = None, *, page: int = 1
    ) -> SearchResult:
        """Return a bounded candidate page, replaying earlier pages for deduplication.

        Args:
            query: Title text, 1–300 characters after whitespace normalization.
                Commas and pipes are rejected because they delimit provider filters.
            limits: Search bounds; defaults apply when omitted.
            page: One-based page whose start must lie within max_results.

        Returns:
            Attributed candidates, pagination and explicit partial-result status.
            Empty matches or a page beyond provider end return complete with no candidates.

        Raises:
            InvalidSearchError: For invalid title text or page, before acquisition.
            asyncio.CancelledError: On cancellation, without further acquisition.
        """
        limits = limits or SearchLimits()
        if not isinstance(query, str):
            raise InvalidSearchError("query must be title text")
        query = " ".join(query.split())
        if not 1 <= len(query) <= 300 or any(char in query for char in ",|"):
            raise InvalidSearchError("query must contain 1–300 characters without comma or pipe")
        if type(page) is not int or page < 1 or (page - 1) * limits.page_size >= limits.max_results:
            raise InvalidSearchError("page starts outside the candidate limit")
        start = (page - 1) * limits.page_size
        end = min(start + limits.page_size, limits.max_results)
        budget = AcquisitionBudget(limits.max_requests, limits.max_seconds, clock=self._clock)
        records: dict[str, ResolvedPaper] = {}
        cursors: set[str] = set()
        cursor = "*"
        status: Literal["complete", "more", "truncated", "failed"] = "complete"
        reasons: tuple[str, ...] = ()
        next_page = None
        try:
            while True:
                budget.remaining_seconds()
                cursors.add(cursor)
                batch = await self._provider.search_titles(
                    query,
                    cursor=cursor,
                    page_size=min(limits.page_size, end - len(records)),
                    budget=budget,
                )
                budget.remaining_seconds()
                if len(batch.candidates) > min(limits.page_size, end - len(records)):
                    raise ProviderMalformedResponseError("provider exceeded requested page size")
                for record in batch.candidates:
                    records.setdefault(record.paper.identifiers.openalex_id.value, record)
                if batch.next_cursor is None:
                    break
                if batch.next_cursor in cursors:
                    status, reasons = "truncated", ("repeated_cursor",)
                    break
                if len(records) == end:
                    if end == limits.max_results:
                        status, reasons = "truncated", ("results",)
                    else:
                        status, next_page = "more", page + 1
                    break
                cursor = batch.next_cursor
        except AcquisitionLimitReached as exc:
            status, reasons = "truncated", (exc.reason,)
        except (
            PaperNotFoundError,
            ProviderMalformedResponseError,
            ProviderRateLimitedError,
            ProviderRetryExhaustedError,
            ProviderTimeoutError,
        ):
            status, reasons = "failed", ("provider_failure",)
        return SearchResult(
            query,
            page,
            tuple(records.values())[start:end],
            next_page,
            status,
            reasons,
            limits,
            budget.requests,
        )
