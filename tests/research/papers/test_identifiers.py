"""Tests for DOI and OpenAlex work identifier normalization."""

import pytest

from research_bridge.research.papers.domain.identifiers import (
    Doi,
    InvalidIdentifierError,
    OpenAlexWorkId,
    parse_identifier,
)


def test_doi_equivalence() -> None:
    a = Doi.parse("10.7717/peerj.4375")
    b = Doi.parse("doi:10.7717/peerj.4375")
    c = Doi.parse("DOI:10.7717/PEERJ.4375")
    d = Doi.parse("https://doi.org/10.7717/peerj.4375")
    e = Doi.parse("http://dx.doi.org/10.7717/peerj.4375")
    assert a.value == "10.7717/peerj.4375"
    assert a == b == c == d == e
    assert a.url == "https://doi.org/10.7717/peerj.4375"


def test_doi_invalid_forms() -> None:
    invalid = [
        "",
        "   ",
        "10.7717",  # missing suffix
        "doi:10.abc/invalid",  # prefix not numeric
        "https://doi.org/",  # empty
        "https://example.org/10.1234/abc",
        "not-a-doi",
        "11.1234/abc",  # must start 10.
    ]
    for raw in invalid:
        with pytest.raises(InvalidIdentifierError):
            Doi.parse(raw)
        with pytest.raises(InvalidIdentifierError):
            parse_identifier(raw)


def test_openalex_equivalence() -> None:
    a = OpenAlexWorkId.parse("W2741809807")
    b = OpenAlexWorkId.parse("w2741809807")
    c = OpenAlexWorkId.parse("https://openalex.org/W2741809807")
    d = OpenAlexWorkId.parse("http://openalex.org/w2741809807")
    e = OpenAlexWorkId.parse("https://api.openalex.org/works/W2741809807")
    assert a.value == "W2741809807"
    assert a == b == c == d == e
    assert a.url == "https://openalex.org/W2741809807"


def test_openalex_invalid_forms() -> None:
    invalid = [
        "",
        "W",  # no digits
        "Wabc",
        "S2741809807",  # wrong prefix
        "https://openalex.org/S2741809807",
        "https://example.org/W2741809807",
        "2741809807",
    ]
    for raw in invalid:
        with pytest.raises(InvalidIdentifierError):
            OpenAlexWorkId.parse(raw)


def test_parse_identifier_dispatch() -> None:
    doi = parse_identifier("10.1234/example")
    assert isinstance(doi, Doi)
    oa = parse_identifier("W12345")
    assert isinstance(oa, OpenAlexWorkId)
    oa2 = parse_identifier("https://openalex.org/W12345")
    assert isinstance(oa2, OpenAlexWorkId)
    with pytest.raises(InvalidIdentifierError):
        parse_identifier("invalid-identifier-xyz")
