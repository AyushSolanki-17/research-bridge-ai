"""OpenAlex adapter implementing the paper provider port.

Provider JSON never crosses into canonical models; payload translation is
isolated here. Network calls are bounded by explicit timeouts and finite
retries. Cancellation propagates immediately without further retries.
"""

from __future__ import annotations

import asyncio
import json
import math
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from research_bridge.ingestion.openalex.infrastructure.settings import OpenAlexSettings
from research_bridge.provenance.domain.evidence import Evidence, InferenceStatus
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
from research_bridge.research.papers.domain.identifiers import Doi, OpenAlexWorkId
from research_bridge.research.papers.domain.paper import (
    Author,
    Paper,
    PaperIdentifiers,
    Topic,
    Venue,
)


def reconstruct_abstract(inverted_index: Any) -> str | None:
    """Reconstruct abstract text from an OpenAlex inverted index.

    Args:
        inverted_index: Provider value for ``abstract_inverted_index``.

    Returns:
        Reconstructed abstract or ``None`` if the index is missing or invalid.
    """
    if inverted_index is None:
        return None
    if not isinstance(inverted_index, dict):
        return None
    if not inverted_index:
        return None
    # Validate shape: dict[str, list[int]]
    positions: list[tuple[int, str]] = []
    for word, indices in inverted_index.items():
        if not isinstance(word, str):
            return None
        if not isinstance(indices, list):
            return None
        for pos in indices:
            if type(pos) is not int or pos < 0:
                return None
            positions.append((pos, word))
    if not positions:
        return None
    # Check for duplicate positions which would indicate malformed index.
    # If duplicates exist, treat as malformed -> None (conservative).
    seen: set[int] = set()
    for pos, _ in positions:
        if pos in seen:
            return None
        seen.add(pos)
    positions.sort(key=lambda x: x[0])
    # Ensure contiguous from 0? OpenAlex may have gaps if truncated, but we still
    # join what we have; gaps just produce joined words.
    words = [word for _, word in positions]
    return " ".join(words)


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_topics(raw: Any) -> tuple[Topic, ...]:
    if not isinstance(raw, list):
        return ()
    topics: list[Topic] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        tid = item.get("id")
        if tid is not None and not isinstance(tid, str):
            tid = None
        name = item.get("display_name")
        if name is not None and not isinstance(name, str):
            name = None
        score = item.get("score")
        if score is not None and not isinstance(score, (int, float)):
            score = None
        # Never coerce unknown to zero.
        score_f = (
            float(score)
            if isinstance(score, (int, float))
            and not isinstance(score, bool)
            and math.isfinite(score)
            and 0 <= score <= 1
            else None
        )
        # Subfield/field/domain may be nested dicts or strings.
        subfield: str | None = None
        field: str | None = None
        domain: str | None = None
        # OpenAlex topics have subfield/field/domain as dicts with display_name
        for key, target in (
            ("subfield", "subfield"),
            ("field", "field"),
            ("domain", "domain"),
        ):
            val = item.get(key)
            if isinstance(val, dict):
                disp = val.get("display_name")
                if isinstance(disp, str):
                    if target == "subfield":
                        subfield = disp
                    elif target == "field":
                        field = disp
                    else:
                        domain = disp
            elif isinstance(val, str):
                if target == "subfield":
                    subfield = val
                elif target == "field":
                    field = val
                else:
                    domain = val
        topics.append(
            Topic(
                id=tid,
                display_name=name,
                score=score_f,
                inference_status=InferenceStatus.INFERRED_PROVIDER,
                subfield=subfield,
                field=field,
                domain=domain,
            )
        )
    return tuple(topics)


def _parse_authors(raw: Any) -> tuple[Author, ...]:
    if not isinstance(raw, list):
        return ()
    authors: list[Author] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        author_obj = entry.get("author")
        name: str | None = None
        orcid: str | None = None
        if isinstance(author_obj, dict):
            disp = author_obj.get("display_name")
            if isinstance(disp, str):
                name = disp
            oid = author_obj.get("orcid")
            if isinstance(oid, str):
                orcid = oid
        if name is None:
            # Fallback: entry may directly contain display_name
            disp = entry.get("display_name")
            if isinstance(disp, str):
                name = disp
        if name is None:
            continue
        position = entry.get("author_position") or entry.get("position")
        pos_str = position if isinstance(position, str) else None
        authors.append(Author(display_name=name, orcid=orcid, position=pos_str))
    return tuple(authors)


def _parse_venue(raw: Any) -> Venue | None:
    if not isinstance(raw, dict):
        return None
    # Try primary_location.source then host_venue/source
    source: Any = None
    primary = raw.get("primary_location")
    if isinstance(primary, dict):
        source = primary.get("source")
    if source is None:
        source = raw.get("host_venue") or raw.get("source")
    venue_name: str | None = None
    venue_id: str | None = None
    if isinstance(source, dict):
        disp = source.get("display_name")
        if isinstance(disp, str):
            venue_name = disp
        vid = (
            source.get("id") or source.get("ids", {}).get("openalex")
            if isinstance(source.get("ids"), dict)
            else None
        )
        # Direct id field
        raw_id = source.get("id")
        if isinstance(raw_id, str):
            venue_id = raw_id
        elif isinstance(vid, str):
            venue_id = vid
    elif isinstance(raw.get("host_venue"), dict):
        hv = raw["host_venue"]
        disp = hv.get("display_name")
        if isinstance(disp, str):
            venue_name = disp
    if venue_name is None and venue_id is None:
        return None
    return Venue(display_name=venue_name, id=venue_id)


def _translate_payload(payload: dict[str, Any], *, observed_at: datetime) -> ResolvedPaper:
    """Translate a validated OpenAlex work payload into canonical models.

    Args:
        payload: Decoded JSON dict for a single work.
        observed_at: Observation time for evidence.

    Returns:
        Canonical :class:`ResolvedPaper`.

    Raises:
        ProviderMalformedResponseError: If required identity fields are missing
            or malformed.
    """
    raw_id = payload.get("id")
    if not isinstance(raw_id, str) or not raw_id:
        raise ProviderMalformedResponseError("missing work id")
    # Payload id is a URL like https://openalex.org/W2741809807
    try:
        openalex_id = OpenAlexWorkId.parse(raw_id)
    except Exception as exc:
        raise ProviderMalformedResponseError(f"malformed work id {raw_id!r}") from exc

    # DOI extraction
    doi_value: Doi | None = None
    # OpenAlex provides doi as https://doi.org/10.xxxx
    raw_doi = payload.get("doi")
    if isinstance(raw_doi, str) and raw_doi:
        try:
            doi_value = Doi.parse(raw_doi)
        except Exception:
            # Also try ids.doi
            doi_value = None
    if doi_value is None:
        ids = payload.get("ids")
        if isinstance(ids, dict):
            maybe_doi = ids.get("doi")
            if isinstance(maybe_doi, str) and maybe_doi:
                try:
                    doi_value = Doi.parse(maybe_doi)
                except Exception:
                    doi_value = None

    title: str | None = None
    raw_title = payload.get("title") or payload.get("display_name")
    if isinstance(raw_title, str) and raw_title.strip():
        title = raw_title.strip()
    else:
        title = None

    pub_date = _parse_date(payload.get("publication_date"))

    venue = _parse_venue(payload)

    authors = _parse_authors(payload.get("authorships"))

    abstract = reconstruct_abstract(payload.get("abstract_inverted_index"))

    # Citation count: preserve None vs 0
    cited_by: int | None = None
    raw_count = payload.get("cited_by_count")
    if type(raw_count) is int and raw_count >= 0:
        cited_by = raw_count
    elif raw_count is None and "cited_by_count" not in payload:
        cited_by = None
    elif raw_count is None:
        cited_by = None
    else:
        # Malformed optional -> treat as None with documented outcome
        cited_by = None

    topics = _parse_topics(payload.get("topics"))

    # Referenced works: list of OpenAlex URLs
    ref_ids: list[OpenAlexWorkId] = []
    raw_refs = payload.get("referenced_works")
    references_complete = isinstance(raw_refs, list)
    if isinstance(raw_refs, list):
        for item in raw_refs:
            if not isinstance(item, str):
                references_complete = False
                continue
            try:
                ref_ids.append(OpenAlexWorkId.parse(item))
            except Exception:
                references_complete = False
                continue

    identifiers = PaperIdentifiers(openalex_id=openalex_id, doi=doi_value)
    paper = Paper(
        identifiers=identifiers,
        title=title,
        publication_date=pub_date,
        venue=venue,
        authors=authors,
        abstract=abstract,
        cited_by_count=cited_by,
        topics=tuple(topics),
        referenced_works=tuple(ref_ids),
        references_complete=references_complete,
    )
    # Evidence identity is stable, observation time does not affect id.
    evidence = Evidence.paper_evidence(
        openalex_id.value,
        observed_at=observed_at,
        source_url=f"https://openalex.org/{openalex_id.value}",
    )
    return ResolvedPaper(paper=paper, evidence=evidence)


class OpenAlexPaperAdapter:
    """HTTP adapter for OpenAlex work lookup and title candidate search.

    The adapter creates a client per call unless the caller supplies one.
    An injected client remains owned by the caller.
    """

    def __init__(
        self,
        settings: OpenAlexSettings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
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
        """Headers or params for auth without leaking key into logs."""
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
            PaperNotFoundError: If the provider returns 404.
            ProviderRateLimitedError: If the provider signals 429.
            ProviderTimeoutError: On timeout.
            ProviderMalformedResponseError: On non-JSON or invalid shape.
            ProviderRetryExhaustedError: When finite retries are exhausted.
            asyncio.CancelledError: If cancelled.
        """
        url = self._build_url(identifier)
        headers = self._build_auth()
        # Add mailto for polite pool if available; not required.
        headers.setdefault("Accept", "application/json")

        client = self._client
        owns = self._owns_client
        if client is None:
            client = httpx.AsyncClient(follow_redirects=True)

        try:
            payload = await self._fetch_with_retries(client, url, headers, str(identifier), budget)
            try:
                return _translate_payload(payload, observed_at=datetime.now(UTC))
            except ProviderMalformedResponseError:
                raise
            except Exception as exc:
                raise ProviderMalformedResponseError("malformed work payload") from exc
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
        url = str(
            httpx.URL(
                f"{self._settings.base_url.rstrip('/')}/works",
                params={
                    "filter": f"title.search:{query}",
                    "cursor": cursor,
                    "per_page": str(page_size),
                },
            )
        )
        client = self._client or httpx.AsyncClient()
        try:
            payload = await self._fetch_with_retries(
                client, url, self._build_auth(), "title search", budget
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
            return CandidatePage(
                tuple(_translate_payload(item, observed_at=observed_at) for item in results),
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
