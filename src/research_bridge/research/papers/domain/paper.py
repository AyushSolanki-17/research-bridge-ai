"""Canonical paper domain models.

Missing optional metadata is preserved as ``None`` rather than invented
or converted to zero. A reported citation count of ``0`` is kept as ``0``,
while a missing count is ``None``.

Provider-reported topics carry their supplied ``score`` unchanged and an
explicit ``INFERRED_PROVIDER`` status. A missing score stays ``None`` and
is never silently converted to ``0``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from research_bridge.provenance.domain.evidence import InferenceStatus
from research_bridge.research.papers.domain.identifiers import Doi, OpenAlexWorkId


@dataclass(frozen=True, slots=True)
class Author:
    """Paper author.

    Attributes:
        display_name: Author name as reported by the provider.
        orcid: ORCID identifier if available.
        position: Authorship position (e.g., ``first``, ``middle``, ``last``).
    """

    display_name: str
    orcid: str | None = None
    position: str | None = None


@dataclass(frozen=True, slots=True)
class Venue:
    """Publication venue.

    Attributes:
        display_name: Venue name as reported.
        id: OpenAlex source ID if available (e.g., ``S123`` or URL).
    """

    display_name: str | None = None
    id: str | None = None


@dataclass(frozen=True, slots=True)
class Topic:
    """Provider-classified topic.

    Attributes:
        id: Topic identifier (e.g., OpenAlex topic URL or ID).
        display_name: Human readable topic name.
        score: Provider-supplied relevance score, or ``None`` if not reported.
        inference_status: Always ``INFERRED_PROVIDER`` for OpenAlex topics.
        subfield: Optional subfield name if provider supplies it.
        field: Optional field name if provider supplies it.
        domain: Optional domain name if provider supplies it.
    """

    id: str | None
    display_name: str | None
    score: float | None
    inference_status: InferenceStatus = InferenceStatus.INFERRED_PROVIDER
    subfield: str | None = None
    field: str | None = None
    domain: str | None = None


@dataclass(frozen=True, slots=True)
class PaperIdentifiers:
    """Stable identifiers for a paper.

    Attributes:
        openalex_id: Normalized OpenAlex work ID.
        doi: Normalized DOI if available.
    """

    openalex_id: OpenAlexWorkId
    doi: Doi | None = None


@dataclass(frozen=True, slots=True)
class Paper:
    """Canonical paper record.

    Attributes:
        identifiers: Stable work identifiers.
        title: Paper title, or ``None`` if not reported.
        publication_date: Publication date, or ``None`` if unknown.
        venue: Publication venue, or ``None`` if unknown.
        authors: Ordered authors as reported.
        abstract: Reconstructed abstract text, or ``None`` if unavailable.
        cited_by_count: Provider-reported citation count, or ``None`` if missing.
            A reported ``0`` is preserved as ``0``.
        topics: Provider-reported topics with explicit inference status.
        referenced_works: Normalized OpenAlex IDs of referenced works.
        references_complete: Whether the provider supplied a valid reference list.
            False distinguishes missing or malformed lists from known empty lists.
    """

    identifiers: PaperIdentifiers
    title: str | None = None
    publication_date: date | None = None
    venue: Venue | None = None
    authors: tuple[Author, ...] = ()
    abstract: str | None = None
    cited_by_count: int | None = None
    topics: tuple[Topic, ...] = ()
    referenced_works: tuple[OpenAlexWorkId, ...] = ()
    references_complete: bool = False
