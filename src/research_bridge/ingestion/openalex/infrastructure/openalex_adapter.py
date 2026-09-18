"""OpenAlex adapter implementing the paper provider port.

Provider JSON is translated by the adjacent translation module. Network calls are
bounded by explicit timeouts and finite retries. Cancellation propagates immediately.
"""

from __future__ import annotations

import asyncio
import json
import math
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from research_bridge.ingestion.openalex.infrastructure.settings import OpenAlexSettings
from research_bridge.ingestion.openalex.infrastructure.translation import (
    reconstruct_abstract as reconstruct_abstract,
)
from research_bridge.ingestion.openalex.infrastructure.translation import (
    translate_work,
)
from research_bridge.knowledge_graph.application import IncomingPage
from research_bridge.research.papers.application.acquisition import AcquisitionBudget
from research_bridge.research.papers.application.errors import (
    PaperNotFoundError,
    ProviderMalformedResponseError,
    ProviderRateLimitedError,
    ProviderRetryExhaustedError,
    ProviderTimeoutError,
)
from research_bridge.research.papers.application.ports import ResolvedPaper
from research_bridge.research.papers.application.search_papers import CandidatePage
from research_bridge.research.papers.domain.identifiers import (
    Doi,
    OpenAlexWorkId,
)


class OpenAlexPaperAdapter:
    """HTTP adapter for work lookup, title search and incoming citation pages.

    The adapter creates a client per call unless the caller supplies one.
    An injected client remains owned by the caller.
    """

    def __init__(
        self,
        settings: OpenAlexSettings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Configure acquisition without opening a network connection.

        Args:
            settings: Validated provider configuration; defaults to environment values.
            client: Optional caller-owned client, which remains open after acquisition.

        Raises:
            ValueError: If environment configuration is invalid.
        """
        self._settings = settings or OpenAlexSettings.from_env()
        self._client = client
        self._owns_client = client is None

    def _build_url(self, identifier: Doi | OpenAlexWorkId) -> str:
        """Build the singleton URL for the given identifier."""
        base = self._settings.base_url.rstrip("/")
        if isinstance(identifier, Doi):
            # Use DOI URL form: https://api.openalex.org/works/https://doi.org/10.xxxx
            return f"{base}/works/https://doi.org/{identifier.value}"
        # OpenAlex ID: https://api.openalex.org/works/W...
        return f"{base}/works/{identifier.value}"

    def _build_auth(self) -> dict[str, str]:
        """Return authentication headers to keep credentials out of query strings."""
        if not self._settings.api_key:
            return {}
        # Prefer header auth to avoid key in URL logs.
        return {"Authorization": f"Bearer {self._settings.api_key}"}

    async def fetch_paper(
        self, identifier: Doi | OpenAlexWorkId, *, budget: AcquisitionBudget | None = None
    ) -> ResolvedPaper:
        """Fetch and translate a single work.

        Bounded: each network request has an explicit timeout and the total
        number of requests is finite. Rate limits and transient failures are
        retried with backoff; cancellation stops further acquisition.

        Args:
            identifier: Canonical DOI or OpenAlex work identifier.
            budget: Optional shared acquisition limits, including retries and redirects.

        Returns:
            Translated paper and stable source evidence.

        Raises:
            AcquisitionLimitReached: If the shared operation budget is exhausted.
            PaperNotFoundError: If the provider returns 404.
            ProviderRateLimitedError: If the provider signals 429.
            ProviderTimeoutError: On timeout.
            ProviderMalformedResponseError: On non-JSON or invalid shape.
            ProviderRetryExhaustedError: When finite retries are exhausted.
            asyncio.CancelledError: If cancelled.
        """
        url = self._build_url(identifier)
        headers = self._build_auth()
        headers.setdefault("Accept", "application/json")

        client = self._client
        owns = self._owns_client
        if client is None:
            client = httpx.AsyncClient(follow_redirects=True)

        try:
            payload = await self._fetch_with_retries(client, url, headers, str(identifier), budget)
            return translate_work(payload, observed_at=datetime.now(UTC))
        finally:
            if owns and client is not None:
                await client.aclose()

    async def search_titles(
        self, query: str, *, cursor: str, page_size: int, budget: AcquisitionBudget
    ) -> CandidatePage:
        """Fetch title-only matches using the same bounded HTTP acquisition as lookup.

        Args:
            query: Application-validated title text.
            cursor: Provider continuation, or '*' for the first page.
            page_size: Requested record count, at most 100.
            budget: Shared search allowance, including retries and redirects.

        Returns:
            Canonical works with attribution and the provider continuation.

        Raises:
            ProviderMalformedResponseError: For malformed list, cursor or work data.
            AcquisitionLimitReached: When physical requests or elapsed time run out.
            ProviderRateLimitedError: If rate limiting prevents acquisition.
            ProviderTimeoutError: If a request times out.
            ProviderRetryExhaustedError: If retry attempts are exhausted.
            asyncio.CancelledError: If the operation is cancelled.
        """
        works, next_cursor = await self._fetch_work_page(
            f"title.search:{query}", cursor=cursor, page_size=page_size, budget=budget
        )
        return CandidatePage(works, next_cursor)

    async def fetch_incoming(
        self, target: OpenAlexWorkId, *, cursor: str, page_size: int, budget: AcquisitionBudget
    ) -> IncomingPage:
        """Fetch works citing a target through OpenAlex's cites filter.

        Args:
            target: Normalized referenced work identifier.
            cursor: Opaque provider continuation, or '*' to begin.
            page_size: Maximum records requested, from 1 through 100.
            budget: Shared allowance for all directions, pages and retries.

        Returns:
            Attributed citing records and the next provider cursor.

        Raises:
            ProviderMalformedResponseError: For invalid page or work data.
            AcquisitionLimitReached: If the shared acquisition allowance runs out.
            ProviderRateLimitedError: If rate limiting prevents acquisition.
            ProviderTimeoutError: If a request times out.
            ProviderRetryExhaustedError: If finite retries fail.
            ValueError: If page size is outside the provider bounds.
            asyncio.CancelledError: If cancelled; no further requests are made.
        """
        works, next_cursor = await self._fetch_work_page(
            f"cites:{target.value}", cursor=cursor, page_size=page_size, budget=budget
        )
        return IncomingPage(works, next_cursor)

    async def _fetch_work_page(
        self, query_filter: str, *, cursor: str, page_size: int, budget: AcquisitionBudget
    ) -> tuple[tuple[ResolvedPaper, ...], str | None]:
        """Translate a bounded filtered page for search and citation acquisition."""
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError("page_size must be an integer from 1 through 100")
        url = str(
            httpx.URL(
                f"{self._settings.base_url.rstrip('/')}/works",
                params={
                    "filter": query_filter,
                    "cursor": cursor,
                    "per_page": str(page_size),
                },
            )
        )
        client = self._client or httpx.AsyncClient()
        try:
            payload = await self._fetch_with_retries(
                client, url, self._build_auth(), "filtered works", budget
            )
            results, meta = payload.get("results"), payload.get("meta")
            if not isinstance(results, list) or not isinstance(meta, dict):
                raise ProviderMalformedResponseError("expected search results and metadata")
            if "next_cursor" not in meta:
                raise ProviderMalformedResponseError("missing search continuation")
            continuation = meta["next_cursor"]
            if continuation is not None and (
                not isinstance(continuation, str) or not continuation or len(continuation) > 4096
            ):
                raise ProviderMalformedResponseError("invalid search continuation")
            if len(results) > page_size or any(not isinstance(item, dict) for item in results):
                raise ProviderMalformedResponseError("invalid search records")
            observed_at = datetime.now(UTC)
            return (
                tuple(translate_work(item, observed_at=observed_at) for item in results),
                continuation,
            )
        finally:
            if self._owns_client:
                await client.aclose()

    async def _fetch_with_retries(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
        identifier: str,
        budget: AcquisitionBudget | None,
    ) -> dict[str, Any]:
        max_retries = self._settings.max_retries
        timeout = self._settings.timeout_seconds
        last_exc: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                attempt_timeout = min(timeout, budget.remaining_seconds()) if budget else timeout
                async with asyncio.timeout(attempt_timeout):
                    request = client.build_request(
                        "GET", url, headers=headers, timeout=attempt_timeout
                    )
                    redirects = 0
                    while True:
                        if budget:
                            budget.consume_request()
                        resp = await client.send(request, follow_redirects=False)
                        if resp.next_request is None:
                            break
                        redirects += 1
                        if redirects > 20:
                            raise httpx.TooManyRedirects("redirect limit exceeded", request=request)
                        request = resp.next_request
            except (httpx.TimeoutException, TimeoutError) as exc:
                last_exc = exc
                if budget:
                    budget.remaining_seconds()
                if attempt == max_retries:
                    if max_retries == 0:
                        raise ProviderTimeoutError(f"timeout for {url}") from exc
                    raise ProviderRetryExhaustedError(
                        f"timeout after {max_retries + 1} attempts for {url}",
                        attempts=max_retries + 1,
                    ) from exc
                # Backoff but bounded; allow cancellation during sleep.
                try:
                    await self._wait(min(0.2 * (2**attempt), 2.0), budget)
                except asyncio.CancelledError:
                    raise
                continue
            except asyncio.CancelledError:
                raise
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt == max_retries:
                    raise ProviderRetryExhaustedError(
                        f"network error after {max_retries + 1} attempts",
                        attempts=max_retries + 1,
                    ) from exc
                try:
                    await self._wait(min(0.2 * (2**attempt), 2.0), budget)
                except asyncio.CancelledError:
                    raise
                continue

            # HTTP status handling
            if resp.status_code == 404:
                raise PaperNotFoundError(str(identifier))
            if resp.status_code == 429:
                last_exc = ProviderRateLimitedError(f"rate limited: {url}")
                if attempt == max_retries:
                    if max_retries == 0:
                        raise ProviderRateLimitedError(f"rate limited: {url}") from last_exc
                    raise ProviderRetryExhaustedError(
                        f"rate limited after {max_retries + 1} attempts",
                        attempts=max_retries + 1,
                    ) from last_exc
                retry_after = resp.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else min(0.2 * (2**attempt), 2.0)
                except ValueError:
                    try:
                        retry_date = parsedate_to_datetime(retry_after or "")
                        delay = (retry_date - datetime.now(UTC)).total_seconds()
                    except (ValueError, TypeError, OverflowError):
                        delay = min(0.2 * (2**attempt), 2.0)
                if not math.isfinite(delay) or delay > 2.0:
                    raise ProviderRateLimitedError("Retry-After exceeds the 2 second wait limit")
                delay = max(delay, 0.0)
                try:
                    await self._wait(delay, budget)
                except asyncio.CancelledError:
                    raise
                continue
            if 500 <= resp.status_code < 600:
                last_exc = RuntimeError(f"transient {resp.status_code}")
                if attempt == max_retries:
                    raise ProviderRetryExhaustedError(
                        f"transient error {resp.status_code} after {max_retries + 1} attempts",
                        attempts=max_retries + 1,
                    ) from last_exc
                try:
                    await self._wait(min(0.2 * (2**attempt), 2.0), budget)
                except asyncio.CancelledError:
                    raise
                continue
            if not 200 <= resp.status_code < 300:
                raise ProviderMalformedResponseError(
                    f"unexpected status {resp.status_code} for {url}"
                )

            # Parse JSON
            try:
                payload = resp.json()
            except (json.JSONDecodeError, ValueError) as exc:
                raise ProviderMalformedResponseError("invalid JSON response") from exc

            if not isinstance(payload, dict):
                raise ProviderMalformedResponseError("expected JSON object for work")

            return payload

        # Should not reach here; raise retries exhausted
        raise ProviderRetryExhaustedError(
            f"exhausted retries for {url}", attempts=max_retries + 1
        ) from last_exc

    async def _wait(self, delay: float, budget: AcquisitionBudget | None) -> None:
        if budget:
            budget.check_wait(delay)
        await asyncio.sleep(delay)
