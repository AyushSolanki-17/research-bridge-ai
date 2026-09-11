"""Validated metadata predicates for an already bounded citation neighborhood."""

from dataclasses import dataclass

from research_bridge.research.papers.domain.paper import Paper


class InvalidFilterError(ValueError):
    """A metadata predicate has an invalid type, range or name."""


def _normalized_name(value: str) -> str:
    return " ".join(value.split()).casefold()


@dataclass(frozen=True)
class ExplorationFilters:
    """Conjunctive predicates on available paper metadata, applied after traversal.

    Attributes:
        year_from: Inclusive publication year lower bound, from 1 through 9999.
        year_to: Inclusive publication year upper bound, from 1 through 9999.
        min_citations: Inclusive nonnegative reported citation-count lower bound.
        max_citations: Inclusive nonnegative reported citation-count upper bound.
        author: Exact normalized display name of any author, at most 300 characters.
        venue: Exact normalized venue display name, at most 300 characters.
        topic: Exact normalized display name of any topic, at most 300 characters.

    None disables a predicate. Missing metadata fails an enabled predicate.
    Names collapse whitespace and ignore case; they do not resolve identities.
    Invalid bounds, reversed ranges or blank names raise InvalidFilterError.
    """

    year_from: int | None = None
    year_to: int | None = None
    min_citations: int | None = None
    max_citations: int | None = None
    author: str | None = None
    venue: str | None = None
    topic: str | None = None

    def __post_init__(self) -> None:
        for name in ("year_from", "year_to", "min_citations", "max_citations"):
            value = getattr(self, name)
            if value is None:
                continue
            minimum = 1 if name.startswith("year_") else 0
            if type(value) is not int or value < minimum:
                raise InvalidFilterError(
                    f"{name} must be an integer greater than or equal to {minimum}"
                )
            if name.startswith("year_") and value > 9999:
                raise InvalidFilterError(f"{name} must be at most 9999")
        for lower, upper in (
            (self.year_from, self.year_to),
            (self.min_citations, self.max_citations),
        ):
            if lower is not None and upper is not None and lower > upper:
                raise InvalidFilterError("filter lower bounds must not exceed upper bounds")
        for name in ("author", "venue", "topic"):
            value = getattr(self, name)
            if value is not None:
                if not isinstance(value, str) or not 1 <= len(value) <= 300 or not value.strip():
                    raise InvalidFilterError(
                        f"{name} must contain 1 through 300 characters and not be blank"
                    )
                normalized = _normalized_name(value)
                if len(normalized) > 300:
                    raise InvalidFilterError(f"normalized {name} must be at most 300 characters")
                object.__setattr__(self, name, normalized)

    def matches(self, paper: Paper) -> bool:
        """Test available metadata without inferring missing values or acquiring data.

        Args:
            paper: Canonical metadata from the acquired neighborhood.

        Returns:
            Whether every enabled predicate matches; no predicates matches any paper.
        """
        year = paper.publication_date.year if paper.publication_date else None
        for value, lower, upper in (
            (year, self.year_from, self.year_to),
            (paper.cited_by_count, self.min_citations, self.max_citations),
        ):
            if lower is not None and (value is None or value < lower):
                return False
            if upper is not None and (value is None or value > upper):
                return False
        if self.author is not None and not any(
            _normalized_name(author.display_name) == self.author for author in paper.authors
        ):
            return False
        if self.venue is not None and (
            paper.venue is None
            or paper.venue.display_name is None
            or _normalized_name(paper.venue.display_name) != self.venue
        ):
            return False
        return self.topic is None or any(
            topic.display_name is not None and _normalized_name(topic.display_name) == self.topic
            for topic in paper.topics
        )
