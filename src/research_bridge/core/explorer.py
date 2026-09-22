"""Deterministic, bounded citation traversal."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from research_bridge.core.budget import AcquisitionBudget, AcquisitionLimitReached
from research_bridge.core.citations import (
    CitationEdge,
    ExplorationCancelled,
    ExplorationLimits,
    ExplorationMode,
    ExplorationResult,
    ExplorationStatus,
    IncomingPageGap,
    MetadataGap,
    UnresolvedReference,
)
from research_bridge.core.errors import (
    InvalidInputError,
    PaperNotFoundError,
    ProviderMalformedResponseError,
    ProviderRateLimitedError,
    ProviderRetryExhaustedError,
    ProviderTimeoutError,
    UnsupportedOperationError,
)
from research_bridge.core.evidence import Evidence, InferenceStatus
from research_bridge.core.filters import ExplorationFilters
from research_bridge.core.identifiers import OpenAlexWorkId, parse_identifier
from research_bridge.core.ports import IncomingCitationPort, PaperProviderPort, ResolvedPaper


def _citation(record: ResolvedPaper, target: OpenAlexWorkId) -> CitationEdge:
    """Create an attributed edge from a citing record's explicit assertion."""
    evidence = record.evidence
    return CitationEdge(
        record.paper.identifiers.openalex_id,
        target,
        target,
        Evidence(
            id=f"{evidence.provider}:citation:{evidence.provider_record_id}:{target.value}",
            provider=evidence.provider,
            provider_record_id=evidence.provider_record_id,
            source_url=evidence.source_url,
            observed_at=evidence.observed_at,
            inference_status=InferenceStatus.REPORTED,
        ),
    )


def _metadata_gap(work_id: OpenAlexWorkId, record: ResolvedPaper) -> MetadataGap | None:
    """Describe unavailable fields without inferring missing metadata."""
    paper = record.paper
    fields = tuple(
        name
        for name in ("title", "authors", "publication_date", "venue", "abstract", "topics")
        if not getattr(paper, name)
    )
    if paper.cited_by_count is None:
        fields += ("cited_by_count",)
    if not paper.references_complete:
        fields += ("referenced_works",)
    return MetadataGap(work_id, fields) if fields else None


@dataclass
class _Traversal:
    """Mutable state owned by one exploration call."""

    provider: PaperProviderPort
    incoming: IncomingCitationPort | None
    bounds: ExplorationLimits
    mode: ExplorationMode
    filters: ExplorationFilters | None
    budget: AcquisitionBudget
    nodes: dict[OpenAlexWorkId, ResolvedPaper] = field(default_factory=dict)
    aliases: dict[OpenAlexWorkId, OpenAlexWorkId] = field(default_factory=dict)
    edges: dict[tuple[OpenAlexWorkId, OpenAlexWorkId], CitationEdge] = field(default_factory=dict)
    unresolved: list[UnresolvedReference] = field(default_factory=list)
    missing: set[OpenAlexWorkId] = field(default_factory=set)
    reasons: list[str] = field(default_factory=list)
    queue: deque[tuple[OpenAlexWorkId, int]] = field(default_factory=deque)
    seed_id: OpenAlexWorkId | None = None
    active_source: OpenAlexWorkId | None = None
    active_target: str = ""
    active_page: tuple[OpenAlexWorkId, str] | None = None

    async def acquire(self, raw_identifier: str) -> ResolvedPaper:
        """Acquire one paper within the operation deadline."""
        try:
            async with asyncio.timeout(self.budget.remaining_seconds()):
                record = await self.provider.fetch_paper(
                    parse_identifier(raw_identifier), budget=self.budget
                )
        except TimeoutError as exc:
            if isinstance(exc, ProviderTimeoutError):
                raise
            raise AcquisitionLimitReached("elapsed_time") from exc
        self.budget.remaining_seconds()
        return record

    def record_stop(self, reason: str) -> None:
        """Record why work stopped and the active unresolved lookup when applicable."""
        self.reasons.append(reason)
        if self.active_page is None:
            self.unresolved.append(
                UnresolvedReference(self.active_source, self.active_target, reason)
            )

    def result(self, status: ExplorationStatus) -> ExplorationResult:
        """Build an immutable public result from the operation state."""
        retained = {
            work_id: record
            for work_id, record in self.nodes.items()
            if self.filters is None or work_id == self.seed_id or self.filters.matches(record.paper)
        }
        retained_edges = tuple(
            edge
            for edge in self.edges.values()
            if self.filters is None or (edge.source in retained and edge.target in retained)
        )
        gaps = tuple(
            gap
            for work_id, record in retained.items()
            if (gap := _metadata_gap(work_id, record)) is not None
        )
        unread = (IncomingPageGap(*self.active_page, self.reasons[-1]),) if self.active_page else ()
        return ExplorationResult(
            seed=self.seed_id,
            nodes=tuple(retained.values()),
            edges=retained_edges,
            unresolved=tuple(self.unresolved),
            incomplete_metadata=gaps,
            status=status,
            stop_reasons=tuple(dict.fromkeys(self.reasons)),
            limits=self.bounds,
            requests=self.budget.requests,
            elapsed_seconds=self.budget.elapsed,
            mode=self.mode,
            unread_incoming_pages=unread,
            filters=self.filters,
            acquired_nodes=len(self.nodes),
            acquired_edges=len(self.edges),
        )

    async def expand_outgoing(self, source: OpenAlexWorkId, depth: int) -> None:
        """Acquire and enqueue explicit references from one citing work."""
        record = self.nodes[source]
        if not record.paper.references_complete:
            self.reasons.append("incomplete_references")
        references = sorted(set(record.paper.referenced_works), key=lambda ref: ref.value)
        for reference in references:
            self.active_source, self.active_target = source, reference.value
            self.budget.remaining_seconds()
            target = self.aliases.get(reference, reference)
            key = (source, target)
            if key in self.edges:
                continue
            if len(self.edges) >= self.bounds.max_edges:
                raise AcquisitionLimitReached("edges")
            if (
                target not in self.nodes
                and reference not in self.missing
                and len(self.nodes) >= self.bounds.max_nodes
            ):
                raise AcquisitionLimitReached("nodes")
            edge = replace(_citation(record, reference), target=target)
            self.edges[key] = edge
            if reference in self.missing:
                self.unresolved.append(UnresolvedReference(source, reference.value, "not_found"))
                continue
            if target in self.nodes:
                continue
            try:
                fetched = await self.acquire(reference.value)
            except PaperNotFoundError:
                self.missing.add(reference)
                self.unresolved.append(UnresolvedReference(source, reference.value, "not_found"))
                self.reasons.append("unresolved_references")
                continue
            canonical = fetched.paper.identifiers.openalex_id
            self.aliases[reference] = canonical
            if canonical != target:
                del self.edges[key]
                self.edges.setdefault((source, canonical), replace(edge, target=canonical))
            if canonical not in self.nodes:
                self.nodes[canonical] = fetched
                self.queue.append((canonical, depth + 1))

    async def expand_incoming(self, source: OpenAlexWorkId, depth: int) -> None:
        """Acquire and enqueue paginated works that explicitly cite one target."""
        assert self.incoming is not None
        cursor: str | None = "*"
        seen_cursors: set[str] = set()
        while cursor is not None:
            self.active_page = (source, cursor)
            self.active_source, self.active_target = None, source.value
            if cursor in seen_cursors:
                raise AcquisitionLimitReached("repeated_cursor")
            seen_cursors.add(cursor)
            try:
                async with asyncio.timeout(self.budget.remaining_seconds()):
                    page = await self.incoming.fetch_incoming(
                        source, cursor=cursor, page_size=100, budget=self.budget
                    )
            except TimeoutError as exc:
                if isinstance(exc, ProviderTimeoutError):
                    raise
                raise AcquisitionLimitReached("elapsed_time") from exc
            self.budget.remaining_seconds()
            for citing in page.works:
                citing_id = citing.paper.identifiers.openalex_id
                self.active_source, self.active_target = citing_id, source.value
                self.budget.remaining_seconds()
                if source not in citing.paper.referenced_works:
                    raise ProviderMalformedResponseError(
                        "incoming record lacks the requested reference assertion"
                    )
                key = (citing_id, source)
                if key in self.edges:
                    continue
                if len(self.edges) >= self.bounds.max_edges:
                    raise AcquisitionLimitReached("edges")
                if citing_id not in self.nodes and len(self.nodes) >= self.bounds.max_nodes:
                    raise AcquisitionLimitReached("nodes")
                self.edges[key] = _citation(citing, source)
                if citing_id not in self.nodes:
                    self.nodes[citing_id] = citing
                    self.queue.append((citing_id, depth + 1))
            cursor = page.next_cursor
        self.active_page = None

    async def traverse(
        self, seed: str | ResolvedPaper, parsed_seed: object | None
    ) -> ExplorationResult:
        """Run breadth-first traversal until the requested scope or a bound ends it."""
        initial = await self.acquire(str(parsed_seed)) if parsed_seed is not None else seed
        assert isinstance(initial, ResolvedPaper)
        self.seed_id = initial.paper.identifiers.openalex_id
        self.nodes[self.seed_id] = initial
        self.queue.append((self.seed_id, 0))
        while self.queue:
            self.budget.remaining_seconds()
            source, depth = self.queue.popleft()
            if depth >= self.bounds.depth:
                continue
            if self.mode != "incoming":
                await self.expand_outgoing(source, depth)
            if self.mode != "outgoing":
                await self.expand_incoming(source, depth)
        return self.result("truncated" if self.reasons else "complete")


class ExploreCitations:
    """Explore citations through injected lookup and incoming provider ports."""

    def __init__(
        self,
        provider: PaperProviderPort,
        *,
        incoming_provider: IncomingCitationPort | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Compose the traversal engine without acquiring data."""
        self._provider = provider
        self._incoming = incoming_provider
        if self._incoming is None and isinstance(provider, IncomingCitationPort):
            self._incoming = provider
        self._clock = clock

    async def execute(
        self,
        seed: str | ResolvedPaper,
        limits: ExplorationLimits | None = None,
        *,
        mode: ExplorationMode = "outgoing",
        filters: ExplorationFilters | None = None,
    ) -> ExplorationResult:
        """Acquire a bounded neighborhood, processing outgoing before incoming."""
        if mode not in ("outgoing", "incoming", "both"):
            raise InvalidInputError("mode must be outgoing, incoming or both")
        if mode != "outgoing" and self._incoming is None:
            raise UnsupportedOperationError("incoming citation acquisition is not configured")
        parsed_seed = parse_identifier(seed) if isinstance(seed, str) else None
        bounds = limits or ExplorationLimits()
        traversal = _Traversal(
            provider=self._provider,
            incoming=self._incoming,
            bounds=bounds,
            mode=mode,
            filters=filters,
            budget=AcquisitionBudget(bounds.max_requests, bounds.max_seconds, clock=self._clock),
            active_target=str(parsed_seed) if parsed_seed else "",
        )
        try:
            return await traversal.traverse(seed, parsed_seed)
        except AcquisitionLimitReached as exc:
            traversal.record_stop(exc.reason)
            return traversal.result("truncated")
        except asyncio.CancelledError as exc:
            traversal.record_stop("cancelled")
            raise ExplorationCancelled(traversal.result("failed")) from exc
        except (
            PaperNotFoundError,
            ProviderMalformedResponseError,
            ProviderRateLimitedError,
            ProviderRetryExhaustedError,
            ProviderTimeoutError,
        ) as exc:
            reason = (
                "seed_not_found"
                if isinstance(exc, PaperNotFoundError) and traversal.seed_id is None
                else "provider_failure"
            )
            traversal.record_stop(reason)
            return traversal.result("failed")
