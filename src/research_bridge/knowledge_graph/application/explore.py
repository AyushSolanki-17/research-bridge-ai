"""Deterministic, bounded outgoing citation exploration."""

import asyncio
import math
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal

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


@dataclass(frozen=True)
class ExplorationLimits:
    """Validated bounds for one outgoing neighborhood.

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


class ExplorationCancelled(asyncio.CancelledError):
    """Cancellation retaining acquired evidence in the result attribute."""

    def __init__(self, result: ExplorationResult) -> None:
        super().__init__("citation exploration cancelled")
        self.result = result


class ExploreOutgoing:
    """Explore outgoing citations through the paper provider boundary.

    Breadth-first discovery and lexical reference ordering make bounded coverage
    reproducible. Each call owns independent state and acquisition accounting.
    """

    def __init__(
        self, provider: PaperProviderPort, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        """Inject a budget-aware provider and monotonic clock."""
        self._provider = provider
        self._clock = clock

    async def execute(
        self, seed: str | ResolvedPaper, limits: ExplorationLimits | None = None
    ) -> ExplorationResult:
        """Acquire a bounded outgoing neighborhood.

        Args:
            seed: Raw DOI/work identifier or already ingested seed record.
            limits: Validated overrides, otherwise documented defaults.

        Returns:
            Acquired data with completion, budget and missing-reference information.

        Raises:
            InvalidIdentifierError: If the raw seed is malformed, before acquisition.
            ExplorationCancelled: Cancellation with the failed partial result attached.
        """
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
                if not record.paper.references_complete:
                    reasons.append("incomplete_references")
                references = sorted(set(record.paper.referenced_works), key=lambda ref: ref.value)
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
                    evidence = Evidence(
                        id=f"{record.evidence.provider}:citation:{record.evidence.provider_record_id}:{reference.value}",
                        provider=record.evidence.provider,
                        provider_record_id=record.evidence.provider_record_id,
                        source_url=record.evidence.source_url,
                        observed_at=record.evidence.observed_at,
                        inference_status=InferenceStatus.REPORTED,
                    )
                    edge = CitationEdge(source, target, reference, evidence)
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
            return result("truncated" if reasons else "complete")
        except AcquisitionLimitReached as exc:
            reasons.append(exc.reason)
            unresolved.append(UnresolvedReference(active_source, active_target, exc.reason))
            return result("truncated")
        except asyncio.CancelledError as exc:
            reasons.append("cancelled")
            unresolved.append(UnresolvedReference(active_source, active_target, "cancelled"))
            raise ExplorationCancelled(result("failed")) from exc
        except (
            PaperNotFoundError,
            ProviderMalformedResponseError,
            ProviderRateLimitedError,
            ProviderRetryExhaustedError,
            ProviderTimeoutError,
        ) as exc:
            reason = "seed_not_found" if isinstance(exc, PaperNotFoundError) else "provider_failure"
            reasons.append(reason)
            unresolved.append(UnresolvedReference(active_source, active_target, reason))
            return result("failed")
