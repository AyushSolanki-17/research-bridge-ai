"""Validated DOI and OpenAlex work identifier value objects.

Accepted DOI forms:
  - Bare DOI: ``10.1234/example`` (case-insensitive, trimmed)
  - ``doi:`` prefix: ``doi:10.1234/example`` or ``DOI:10.1234/example``
  - URL: ``https://doi.org/10.1234/example``,
    ``http://doi.org/10.1234/example``,
    ``https://dx.doi.org/10.1234/example``,
    ``http://dx.doi.org/10.1234/example`` (case-insensitive host)

Accepted OpenAlex work identifier forms:
  - Bare: ``W2741809807`` or ``w2741809807`` (case-insensitive)
  - URL: ``https://openalex.org/W2741809807``,
    ``http://openalex.org/W2741809807``,
    ``https://api.openalex.org/works/W2741809807`` (case-insensitive host)

Normalization:
  - DOI: lowercased, stripped, without prefix or host.
  - OpenAlex: uppercased ``W`` followed by digits, without URL prefix.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_DOI_CORE_PATTERN = re.compile(r"^10\.\d{4,9}/[-._;()/:a-z0-9]+$", re.IGNORECASE)
_DOI_PREFIX_RE = re.compile(r"^doi:\s*", re.IGNORECASE)
_DOI_URL_RE = re.compile(r"^https?://(?:dx\.)?doi\.org/\s*", re.IGNORECASE)
_OPENALEX_BARE_RE = re.compile(r"^W\d+$", re.IGNORECASE)
_OPENALEX_URL_RE = re.compile(r"^https?://(?:api\.)?openalex\.org/(?:works/)?\s*", re.IGNORECASE)


class InvalidIdentifierError(ValueError):
    """Raised when a raw identifier does not match any supported form."""

    def __init__(self, raw: str, reason: str) -> None:
        super().__init__(f"invalid identifier {raw!r}: {reason}")
        self.raw = raw
        self.reason = reason


def _extract_doi_core(raw: str) -> str | None:
    """Extract DOI core from a raw string if it matches any accepted form."""
    trimmed = raw.strip()
    if not trimmed:
        return None
    # URL form has highest priority to avoid stripping doi: inside URL.
    url_match = _DOI_URL_RE.match(trimmed)
    if url_match:
        core = trimmed[url_match.end() :].strip()
        # Remove trailing slash or fragment that sometimes appears.
        core = core.split("#")[0].split("?")[0].rstrip("/")
        return core
    prefix_match = _DOI_PREFIX_RE.match(trimmed)
    if prefix_match:
        core = trimmed[prefix_match.end() :].strip()
        core = core.split("#")[0].split("?")[0].rstrip("/")
        return core
    # Bare DOI: must look like a DOI itself.
    if _DOI_CORE_PATTERN.match(trimmed):
        core = trimmed.split("#")[0].split("?")[0].rstrip("/")
        return core
    # Bare DOI with trailing slash handling still fails pattern if extra slash
    # Try stripped trailing slash then pattern.
    stripped = trimmed.rstrip("/")
    if _DOI_CORE_PATTERN.match(stripped):
        return stripped
    return None


def _extract_openalex_core(raw: str) -> str | None:
    """Extract OpenAlex core from a raw string if it matches any accepted form."""
    trimmed = raw.strip()
    if not trimmed:
        return None
    url_match = _OPENALEX_URL_RE.match(trimmed)
    if url_match:
        core = trimmed[url_match.end() :].strip()
        core = core.split("#")[0].split("?")[0].rstrip("/")
        return core
    # Bare form.
    core = trimmed
    if _OPENALEX_BARE_RE.fullmatch(core):
        return core
    return None


@dataclass(frozen=True, slots=True)
class Doi:
    """Validated DOI value object.

    Attributes:
        value: Normalized DOI (lowercased, without prefix or URL).
    """

    value: str

    def __post_init__(self) -> None:
        if not _DOI_CORE_PATTERN.fullmatch(self.value):
            raise InvalidIdentifierError(self.value, "malformed DOI core")
        object.__setattr__(self, "value", self.value.lower())

    @classmethod
    def parse(cls, raw: str) -> Doi:
        """Parse a raw DOI in any supported form.

        Args:
            raw: User supplied DOI string.

        Returns:
            Normalized :class:`Doi`.

        Raises:
            InvalidIdentifierError: If ``raw`` does not match accepted DOI forms.
        """
        core = _extract_doi_core(raw)
        if core is None:
            raise InvalidIdentifierError(raw, "unsupported DOI form")
        normalized = core.lower()
        if not _DOI_CORE_PATTERN.match(normalized):
            raise InvalidIdentifierError(raw, "malformed DOI")
        return cls(value=normalized)

    def __str__(self) -> str:
        return self.value

    @property
    def url(self) -> str:
        """Canonical https://doi.org URL for this DOI."""
        return f"https://doi.org/{self.value}"


@dataclass(frozen=True, slots=True)
class OpenAlexWorkId:
    """Validated OpenAlex work identifier.

    Attributes:
        value: Normalized identifier (uppercase ``W`` + digits).
    """

    value: str

    def __post_init__(self) -> None:
        if not _OPENALEX_BARE_RE.fullmatch(self.value):
            raise InvalidIdentifierError(self.value, "malformed OpenAlex work ID")
        # Enforce canonical uppercase.
        if self.value != self.value.upper():
            raise InvalidIdentifierError(self.value, "OpenAlex work ID must be uppercase")

    @classmethod
    def parse(cls, raw: str) -> OpenAlexWorkId:
        """Parse a raw OpenAlex work identifier in any supported form.

        Args:
            raw: User supplied identifier string.

        Returns:
            Normalized :class:`OpenAlexWorkId`.

        Raises:
            InvalidIdentifierError: If ``raw`` does not match accepted forms.
        """
        core = _extract_openalex_core(raw)
        if core is None:
            raise InvalidIdentifierError(raw, "unsupported OpenAlex work ID form")
        normalized = core.upper()
        if not _OPENALEX_BARE_RE.fullmatch(normalized):
            raise InvalidIdentifierError(raw, "malformed OpenAlex work ID")
        return cls(value=normalized)

    def __str__(self) -> str:
        return self.value

    @property
    def url(self) -> str:
        """Canonical https://openalex.org URL for this work."""
        return f"https://openalex.org/{self.value}"

    @property
    def api_url(self) -> str:
        """Canonical API URL for this work."""
        return f"https://api.openalex.org/works/{self.value}"


def parse_identifier(raw: str) -> Doi | OpenAlexWorkId:
    """Parse a raw string as either DOI or OpenAlex work identifier.

    Tries DOI first, then OpenAlex. This order is deterministic and
    does not depend on paper-specific branches.

    Args:
        raw: User supplied identifier.

    Returns:
        A :class:`Doi` or :class:`OpenAlexWorkId`.

    Raises:
        InvalidIdentifierError: If ``raw`` matches neither form.
    """
    # Check OpenAlex URL first to avoid misclassifying W-like DOI suffix.
    # But Doi core never starts with W alone, so order barely matters.
    # Try DOI extraction explicitly; if it yields a valid DOI core, prefer DOI.
    doi_core = _extract_doi_core(raw)
    if doi_core is not None:
        try:
            return Doi.parse(raw)
        except InvalidIdentifierError:
            pass
    oa_core = _extract_openalex_core(raw)
    if oa_core is not None:
        try:
            return OpenAlexWorkId.parse(raw)
        except InvalidIdentifierError:
            pass
    raise InvalidIdentifierError(raw, "unsupported identifier form")
