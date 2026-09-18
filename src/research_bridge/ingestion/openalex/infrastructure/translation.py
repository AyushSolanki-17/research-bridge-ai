"""Translate OpenAlex work payloads into canonical papers and source evidence.

These pure transformations preserve unknown metadata and explicit reference gaps.
Acquisition, retries and client ownership belong to the HTTP adapter.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from research_bridge.provenance.domain.evidence import Evidence, InferenceStatus
from research_bridge.research.papers.application.errors import ProviderMalformedResponseError
from research_bridge.research.papers.application.ports import ResolvedPaper
from research_bridge.research.papers.domain.identifiers import (
    Doi,
    InvalidIdentifierError,
    OpenAlexWorkId,
)
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
        Reconstructed abstract, or None for missing, empty or invalid indexes.
        Tokens must be nonempty and positions must be unique and contiguous from zero;
        incomplete text is not joined across missing positions.
    """
    if inverted_index is None:
        return None
    if not isinstance(inverted_index, dict):
        return None
    if not inverted_index:
        return None
    positions: list[tuple[int, str]] = []
    for word, indices in inverted_index.items():
        if not isinstance(word, str) or not word.strip():
            return None
        if not isinstance(indices, list):
            return None
        for pos in indices:
            if type(pos) is not int or pos < 0:
                return None
            positions.append((pos, word))
    if not positions:
        return None
    # Multiple words at the same position cannot be reconstructed faithfully.
    seen: set[int] = set()
    for pos, _ in positions:
        if pos in seen:
            return None
        seen.add(pos)
    positions.sort(key=lambda x: x[0])
    # Joining across missing words could change the meaning of the source text.
    if any(pos != expected for expected, (pos, _) in enumerate(positions)):
        return None
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
            if isinstance(score, (int, float)) and not isinstance(score, bool) and 0 <= score <= 1
            else None
        )
        # Subfield/field/domain may be nested dicts or strings.
        subfield: str | None = None
        field: str | None = None
        domain: str | None = None
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
            # Legacy records can carry the display name directly on the authorship.
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
    # Prefer current location metadata, retaining legacy venue fallbacks.
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


def translate_work(payload: dict[str, Any], *, observed_at: datetime) -> ResolvedPaper:
    """Translate an OpenAlex work payload into canonical models.

    Expected identifier failures follow the required/optional metadata rules.
    Unexpected translation defects propagate to the caller for diagnosis.

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
    try:
        openalex_id = OpenAlexWorkId.parse(raw_id)
    except InvalidIdentifierError as exc:
        raise ProviderMalformedResponseError(f"malformed work id {raw_id!r}") from exc

    doi_value: Doi | None = None
    raw_doi = payload.get("doi")
    if isinstance(raw_doi, str) and raw_doi:
        try:
            doi_value = Doi.parse(raw_doi)
        except InvalidIdentifierError:
            # An invalid primary DOI must not hide a valid secondary identifier.
            doi_value = None
    if doi_value is None:
        ids = payload.get("ids")
        if isinstance(ids, dict):
            maybe_doi = ids.get("doi")
            if isinstance(maybe_doi, str) and maybe_doi:
                try:
                    doi_value = Doi.parse(maybe_doi)
                except InvalidIdentifierError:
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

    # Zero is reported data; malformed or missing counts remain unknown.
    raw_count = payload.get("cited_by_count")
    cited_by = raw_count if type(raw_count) is int and raw_count >= 0 else None

    topics = _parse_topics(payload.get("topics"))

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
            except InvalidIdentifierError:
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
    # Observation time must not change the evidence identity.
    evidence = Evidence.paper_evidence(
        openalex_id.value,
        observed_at=observed_at,
        source_url=f"https://openalex.org/{openalex_id.value}",
    )
    return ResolvedPaper(paper=paper, evidence=evidence)
