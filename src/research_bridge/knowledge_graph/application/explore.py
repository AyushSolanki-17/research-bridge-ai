"""Deterministic, bounded citation exploration in either or both directions."""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal

from research_bridge.knowledge_graph.application.incoming import IncomingCitationPort
from research_bridge.provenance.domain.evidence import Evidence, InferenceStatus
from research_bridge.research.papers.application import (
    AcquisitionBudget,
    AcquisitionLimitReached,
    PaperProviderPort,
    ResolvedPaper,
)
from research_bridge.research.papers.application.errors import (
    PaperNotFoundError,
    ProviderMalformedResponseError,
    ProviderRateLimitedError,
    ProviderRetryExhaustedError,
    ProviderTimeoutError,
)
from research_bridge.research.papers.domain.identifiers import OpenAlexWorkId, parse_identifier

ExplorationMode = Literal["outgoing", "incoming", "both"]


def _citation(record: ResolvedPaper, target: OpenAlexWorkId) -> CitationEdge:
    """Preserve the citing record's explicit reference assertion and attribution."""
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


@dataclass(frozen=True)
class ExplorationLimits:
    """Validated bounds shared by all directions in one neighborhood.

    Attributes:
        depth: Citation hops, from 1 through 3; seed is at depth zero.
        max_nodes: Paper limit including the seed, from 1 through 500.
        max_edges: Unique directed edge limit, from 1 through 2000.
        max_requests: Physical request limit including retries, from 1 through 1000.
        max_seconds: Positive finite elapsed limit, at most 120 seconds.
    """

    depth: int = 1
    max_nodes: int = 50
    max_edges: int = 200
    max_requests: int = 100
    max_seconds: float = 30.0

    def __post_init__(self) -> None:
        for name, maximum in (
            ("depth", 3),
            ("max_nodes", 500),
            ("max_edges", 2000),
            ("max_requests", 1000),
        ):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f"{name} must be an integer in [1, {maximum}]")
        if (
            isinstance(self.max_seconds, bool)
            or not math.isfinite(self.max_seconds)
            or not 0 < self.max_seconds <= 120
        ):
            raise ValueError("max_seconds must be finite and in (0, 120]")


@dataclass(frozen=True)
class CitationEdge:
    """Reported citation from source to target, with its original reference identity.

    Attributes:
        source: Canonical citing work.
        target: Canonical referenced work if resolved; otherwise original identifier.
        referenced_id: Identifier asserted by the source before merge resolution.
        evidence: Source record and observation supporting this reference assertion.
    """

    source: OpenAlexWorkId
    target: OpenAlexWorkId
    referenced_id: OpenAlexWorkId
    evidence: Evidence


@dataclass(frozen=True)
class UnresolvedReference:
    """An acquired reference whose target could not be resolved.

    Attributes:
        source: Citing work, absent only for seed acquisition failure.
        target: Requested target identifier.
        reason: Missing work, provider failure, cancellation or budget limit.
    """

    source: OpenAlexWorkId | None
    target: str
    reason: str


@dataclass(frozen=True)
class MetadataGap:
    """Unavailable metadata fields for an acquired work.

    Attributes:
        work_id: Canonical work identity.
        fields: Field names with unavailable values; no facts are inferred.
    """

    work_id: OpenAlexWorkId
    fields: tuple[str, ...]


@dataclass(frozen=True)
class IncomingPageGap:
    """An incoming page that was not fully processed.

    Attributes:
        target: Referenced work whose citing neighborhood remains incomplete.
        cursor: Provider page that failed or was only partially processed.
        reason: Budget limit, repeated cursor, provider failure or cancellation.
    """

    target: OpenAlexWorkId
    cursor: str
    reason: str


@dataclass(frozen=True)
class ExplorationResult:
    """Immutable acquired neighborhood and explicit completion evidence.

    Attributes:
        seed: Resolved seed identity, or None if acquisition failed.
        nodes: Unique acquired papers in breadth-first discovery order.
        edges: Unique directed citations in stable traversal order.
        unresolved: References that could not be acquired.
        incomplete_metadata: Missing fields on acquired records.
        status: Complete within scope, truncated, or failed acquisition.
        stop_reasons: Machine-readable explanations, empty for complete results.
        limits: Applied validated bounds.
        requests: Physical provider requests consumed, including seed and retries.
        elapsed_seconds: Monotonic operation duration.
        mode: Direction followed during discovery; edges always mean citing to cited.
        unread_incoming_pages: Incoming pages interrupted during acquisition or processing.
    """

    seed: OpenAlexWorkId | None
    nodes: tuple[ResolvedPaper, ...]
    edges: tuple[CitationEdge, ...]
    unresolved: tuple[UnresolvedReference, ...]
    incomplete_metadata: tuple[MetadataGap, ...]
    status: Literal["complete", "truncated", "failed"]
    stop_reasons: tuple[str, ...]
    limits: ExplorationLimits
    requests: int
    elapsed_seconds: float
    mode: ExplorationMode = "outgoing"
    unread_incoming_pages: tuple[IncomingPageGap, ...] = ()


class ExplorationCancelled(asyncio.CancelledError):
    """Cancellation retaining acquired evidence.

    Attributes:
        result: Failed partial graph with the cancellation stop reason.
    """

    def __init__(self, result: ExplorationResult) -> None:
        """Attach the graph acquired before cancellation.

        Args:
            result: Partial exploration outcome retained for caller inspection.
        """
        super().__init__("citation exploration cancelled")
        self.result = result


class ExploreCitations:
    """Explore citations through lookup and incoming acquisition boundaries.

    Breadth-first discovery and lexical reference ordering make bounded coverage
    reproducible. Each call owns independent state and acquisition accounting.
    """

    def __init__(
        self,
        provider: PaperProviderPort,
        *,
        incoming_provider: IncomingCitationPort | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Compose exploration without acquiring data.

        Args:
            provider: Acquisition boundary accounting for every physical request.
            incoming_provider: Incoming boundary, defaulting to provider if supported.
            clock: Monotonic seconds source, injectable for deterministic tests.
        """
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
    ) -> ExplorationResult:
        """Acquire a bounded neighborhood, processing outgoing before incoming.

        Args:
            seed: Raw DOI/work identifier or already ingested seed record.
            limits: Validated overrides, otherwise documented defaults.
            mode: Outgoing, incoming, or both directions at every expanded node.

        Returns:
            Acquired data with completion, budget and missing-reference information.

        Raises:
            InvalidIdentifierError: If the raw seed is malformed, before acquisition.
            ExplorationCancelled: Cancellation with the failed partial result attached.
            ValueError: If mode is invalid or incoming acquisition is not configured.
        """
        if mode not in ("outgoing", "incoming", "both"):
            raise ValueError("mode must be outgoing, incoming or both")
        if mode != "outgoing" and self._incoming is None:
            raise ValueError("incoming citation acquisition is not configured")
        identifier = parse_identifier(seed) if isinstance(seed, str) else None
        bounds = limits or ExplorationLimits()
        budget = AcquisitionBudget(bounds.max_requests, bounds.max_seconds, clock=self._clock)
        nodes: dict[OpenAlexWorkId, ResolvedPaper] = {}
        aliases: dict[OpenAlexWorkId, OpenAlexWorkId] = {}
        edges: dict[tuple[OpenAlexWorkId, OpenAlexWorkId], CitationEdge] = {}
        unresolved: list[UnresolvedReference] = []
        missing: set[OpenAlexWorkId] = set()
        reasons: list[str] = []
        seed_id: OpenAlexWorkId | None = None
        active_source: OpenAlexWorkId | None = None
        active_target = str(identifier) if identifier else ""
        active_page: tuple[OpenAlexWorkId, str] | None = None

        def record_stop(reason: str) -> None:
            reasons.append(reason)
            if active_page is None:
                unresolved.append(UnresolvedReference(active_source, active_target, reason))

        def result(status: Literal["complete", "truncated", "failed"]) -> ExplorationResult:
            gaps = []
            for work_id, record in nodes.items():
                paper = record.paper
                fields = tuple(
                    name
                    for name in (
                        "title",
                        "authors",
                        "publication_date",
                        "venue",
                        "abstract",
                        "topics",
                    )
                    if not getattr(paper, name)
                )
                if paper.cited_by_count is None:
                    fields += ("cited_by_count",)
                if not paper.references_complete:
                    fields += ("referenced_works",)
                if fields:
                    gaps.append(MetadataGap(work_id, fields))
            return ExplorationResult(
                seed_id,
                tuple(nodes.values()),
                tuple(edges.values()),
                tuple(unresolved),
                tuple(gaps),
                status,
                tuple(dict.fromkeys(reasons)),
                bounds,
                budget.requests,
                budget.elapsed,
                mode,
                (IncomingPageGap(*active_page, reasons[-1]),) if active_page else (),
            )

        async def acquire(raw: str) -> ResolvedPaper:
            try:
                async with asyncio.timeout(budget.remaining_seconds()):
                    record = await self._provider.fetch_paper(parse_identifier(raw), budget=budget)
            except TimeoutError as exc:
                if isinstance(exc, ProviderTimeoutError):
                    raise
                raise AcquisitionLimitReached("elapsed_time") from exc
            budget.remaining_seconds()
            return record

        try:
            initial = await acquire(str(identifier)) if identifier else seed
            assert isinstance(initial, ResolvedPaper)
            seed_id = initial.paper.identifiers.openalex_id
            nodes[seed_id] = initial
            queue = deque([(seed_id, 0)])
            while queue:
                budget.remaining_seconds()
                source, depth = queue.popleft()
                if depth >= bounds.depth:
                    continue
                record = nodes[source]
                if mode != "incoming" and not record.paper.references_complete:
                    reasons.append("incomplete_references")
                references = (
                    sorted(set(record.paper.referenced_works), key=lambda ref: ref.value)
                    if mode != "incoming"
                    else []
                )
                for reference in references:
                    active_source, active_target = source, reference.value
                    budget.remaining_seconds()
                    target = aliases.get(reference, reference)
                    key = (source, target)
                    if key in edges:
                        continue
                    if len(edges) >= bounds.max_edges:
                        raise AcquisitionLimitReached("edges")
                    if (
                        target not in nodes
                        and reference not in missing
                        and len(nodes) >= bounds.max_nodes
                    ):
                        raise AcquisitionLimitReached("nodes")
                    edge = replace(_citation(record, reference), target=target)
                    edges[key] = edge
                    if reference in missing:
                        unresolved.append(UnresolvedReference(source, reference.value, "not_found"))
                        continue
                    if target in nodes:
                        continue
                    try:
                        fetched = await acquire(reference.value)
                    except PaperNotFoundError:
                        missing.add(reference)
                        unresolved.append(UnresolvedReference(source, reference.value, "not_found"))
                        reasons.append("unresolved_references")
                        continue
                    canonical = fetched.paper.identifiers.openalex_id
                    aliases[reference] = canonical
                    if canonical != target:
                        del edges[key]
                        edges.setdefault((source, canonical), replace(edge, target=canonical))
                    if canonical not in nodes:
                        nodes[canonical] = fetched
                        queue.append((canonical, depth + 1))
                if mode != "outgoing":
                    assert self._incoming is not None
                    cursor: str | None = "*"
                    seen_cursors: set[str] = set()
                    while cursor is not None:
                        active_page = (source, cursor)
                        active_source, active_target = None, source.value
                        if cursor in seen_cursors:
                            raise AcquisitionLimitReached("repeated_cursor")
                        seen_cursors.add(cursor)
                        try:
                            async with asyncio.timeout(budget.remaining_seconds()):
                                page = await self._incoming.fetch_incoming(
                                    source, cursor=cursor, page_size=100, budget=budget
                                )
                        except TimeoutError as exc:
                            if isinstance(exc, ProviderTimeoutError):
                                raise
                            raise AcquisitionLimitReached("elapsed_time") from exc
                        budget.remaining_seconds()
                        for citing in page.works:
                            citing_id = citing.paper.identifiers.openalex_id
                            active_source, active_target = citing_id, source.value
                            budget.remaining_seconds()
                            if source not in citing.paper.referenced_works:
                                raise ProviderMalformedResponseError(
                                    "incoming record lacks the requested reference assertion"
                                )
                            key = (citing_id, source)
                            if key in edges:
                                continue
                            if len(edges) >= bounds.max_edges:
                                raise AcquisitionLimitReached("edges")
                            if citing_id not in nodes and len(nodes) >= bounds.max_nodes:
                                raise AcquisitionLimitReached("nodes")
                            edges[key] = _citation(citing, source)
                            if citing_id not in nodes:
                                nodes[citing_id] = citing
                                queue.append((citing_id, depth + 1))
                        cursor = page.next_cursor
                    active_page = None
            return result("truncated" if reasons else "complete")
        except AcquisitionLimitReached as exc:
            record_stop(exc.reason)
            return result("truncated")
        except asyncio.CancelledError as exc:
            record_stop("cancelled")
            raise ExplorationCancelled(result("failed")) from exc
        except (
            PaperNotFoundError,
            ProviderMalformedResponseError,
            ProviderRateLimitedError,
            ProviderRetryExhaustedError,
            ProviderTimeoutError,
        ) as exc:
            reason = (
                "seed_not_found"
                if isinstance(exc, PaperNotFoundError) and seed_id is None
                else "provider_failure"
            )
            record_stop(reason)
            return result("failed")


# Preserve the original library entrypoint and its outgoing default.
ExploreOutgoing = ExploreCitations
