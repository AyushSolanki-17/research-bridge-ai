"""Citation exploration inputs, results, and public status values."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Literal

from research_bridge.core.errors import InvalidLimitsError
from research_bridge.core.evidence import Evidence
from research_bridge.core.filters import ExplorationFilters
from research_bridge.core.identifiers import OpenAlexWorkId
from research_bridge.core.ports import ResolvedPaper

ExplorationMode = Literal["outgoing", "incoming", "both"]
ExplorationStatus = Literal["complete", "truncated", "failed"]


@dataclass(frozen=True, slots=True)
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
        """Reject values outside the supported work bounds."""
        for name, maximum in (
            ("depth", 3),
            ("max_nodes", 500),
            ("max_edges", 2000),
            ("max_requests", 1000),
        ):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise InvalidLimitsError(f"{name} must be an integer in [1, {maximum}]")
        if (
            isinstance(self.max_seconds, bool)
            or not math.isfinite(self.max_seconds)
            or not 0 < self.max_seconds <= 120
        ):
            raise InvalidLimitsError("max_seconds must be finite and in (0, 120]")


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
class MetadataGap:
    """Unavailable metadata fields for an acquired work.

    Attributes:
        work_id: Canonical work identity.
        fields: Field names with unavailable values; no facts are inferred.
    """

    work_id: OpenAlexWorkId
    fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
class ExplorationResult:
    """Immutable acquired neighborhood and explicit completion evidence.

    Attributes:
        seed: Resolved seed identity, or None if acquisition failed.
        nodes: Retained papers in breadth-first discovery order; seed is always retained.
        edges: Unique directed citations in stable traversal order.
        unresolved: References that could not be acquired.
        incomplete_metadata: Missing fields on retained records.
        status: Complete within scope, truncated, or failed acquisition.
        stop_reasons: Machine-readable explanations, empty for complete results.
        limits: Applied validated bounds.
        requests: Physical provider requests consumed, including seed and retries.
        elapsed_seconds: Monotonic operation duration.
        mode: Direction followed during discovery; edges always mean citing to cited.
        unread_incoming_pages: Incoming pages interrupted during acquisition or processing.
        filters: Normalized predicates, or None for the original unfiltered result.
        filter_scope: Filters affect returned results within the bounded neighborhood.
        acquired_nodes: Paper count before filtering, including the seed.
        acquired_edges: Citation count before filtering, including unresolved endpoints.
    """

    seed: OpenAlexWorkId | None
    nodes: tuple[ResolvedPaper, ...]
    edges: tuple[CitationEdge, ...]
    unresolved: tuple[UnresolvedReference, ...]
    incomplete_metadata: tuple[MetadataGap, ...]
    status: ExplorationStatus
    stop_reasons: tuple[str, ...]
    limits: ExplorationLimits
    requests: int
    elapsed_seconds: float
    mode: ExplorationMode = "outgoing"
    unread_incoming_pages: tuple[IncomingPageGap, ...] = ()
    filters: ExplorationFilters | None = None
    filter_scope: Literal["returned_results"] = "returned_results"
    acquired_nodes: int = 0
    acquired_edges: int = 0


class ExplorationCancelled(asyncio.CancelledError):
    """Cancellation retaining the graph acquired before interruption."""

    def __init__(self, result: ExplorationResult) -> None:
        """Attach the partial result to the cancellation signal."""
        super().__init__("citation exploration cancelled")
        self.result = result
