"""Metadata filtering and evidence inspection through every supported caller."""

import asyncio
import json
from dataclasses import asdict, replace
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from research_bridge.api.app import create_app
from research_bridge.cli import _json_default, run
from research_bridge.knowledge_graph.application import (
    ExplorationCancelled,
    ExplorationFilters,
    ExplorationLimits,
    ExplorationMode,
    ExploreCitations,
    InvalidFilterError,
)
from research_bridge.provenance.domain.evidence import Evidence
from research_bridge.research.papers.application import ResolvedPaper
from research_bridge.research.papers.application.errors import ProviderMalformedResponseError
from research_bridge.research.papers.domain.paper import Author, Topic, Venue
from tests.knowledge_graph.test_explore import Clock, Provider, paper
from tests.knowledge_graph.test_incoming import CitationProvider


def rich_record(work: str, *references: str) -> ResolvedPaper:
    """Create a paper with known range boundaries and normalized-name candidates."""
    record = paper(work, *references)
    return replace(
        record,
        paper=replace(
            record.paper,
            publication_date=date(2020, 12, 31),
            cited_by_count=0,
            authors=(Author("Ada Lovelace"), Author("Grace Hopper")),
            venue=Venue("Journal of Tests", "S1"),
            topics=(Topic("T1", "Graph Theory", None),),
        ),
    )


@pytest.mark.parametrize(
    "values,expected",
    [
        ({"year_from": 2020, "year_to": 2020}, True),
        ({"year_from": 2021}, False),
        ({"year_to": 2019}, False),
        ({"min_citations": 0, "max_citations": 0}, True),
        ({"min_citations": 1}, False),
        ({"author": "  GRACE\tHopper "}, True),
        ({"author": "Hopper"}, False),
        ({"venue": " JOURNAL  of Tests "}, True),
        ({"venue": "S1"}, False),
        ({"topic": "GRAPH Theory"}, True),
        ({"topic": "T1"}, False),
        (
            {
                "year_from": 2020,
                "max_citations": 0,
                "author": "Ada Lovelace",
                "venue": "Journal of Tests",
                "topic": "Graph Theory",
            },
            True,
        ),
        ({"year_from": 2020, "author": "Unknown"}, False),
    ],
)
def test_metadata_predicates(values: dict[str, object], expected: bool) -> None:
    """Use inclusive ranges, any matching author/topic, exact names and conjunction."""
    assert ExplorationFilters(**values).matches(rich_record("W2").paper) is expected


@pytest.mark.parametrize(
    "values",
    [
        {"year_from": 1},
        {"year_to": 9999},
        {"min_citations": 0},
        {"max_citations": 0},
        {"author": "Ada Lovelace"},
        {"venue": "Journal of Tests"},
        {"topic": "Graph Theory"},
    ],
)
def test_missing_metadata_fails_active_predicate(values: dict[str, object]) -> None:
    """Unknown values never become a zero, name match or inferred topic."""
    assert not ExplorationFilters(**values).matches(paper("W2").paper)
    assert ExplorationFilters().matches(paper("W2").paper)


@pytest.mark.parametrize(
    "values",
    [
        {"year_from": 0},
        {"year_to": 10000},
        {"year_from": True},
        {"year_to": 2020.5},
        {"min_citations": -1},
        {"max_citations": False},
        {"min_citations": "0"},
        {"year_from": 2021, "year_to": 2020},
        {"min_citations": 2, "max_citations": 1},
        {"author": " "},
        {"venue": ""},
        {"topic": "x" * 301},
        {"author": 1},
    ],
)
def test_invalid_filters(values: dict[str, object]) -> None:
    """Reject invalid filter contracts before a caller can begin acquisition."""
    with pytest.raises(InvalidFilterError):
        ExplorationFilters(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["outgoing", "incoming", "both"])
async def test_filtering_preserves_expansion_and_scope(mode: ExplorationMode) -> None:
    """Discover matches beyond excluded intermediates without inventing shortcut edges."""
    records = [paper("W1", "W2"), paper("W2", "W3", "W1"), rich_record("W3", "W2")]
    unfiltered_provider = CitationProvider(records)
    filtered_provider = CitationProvider(records)
    bounds = ExplorationLimits(depth=2)
    unfiltered = await ExploreCitations(unfiltered_provider).execute("W1", bounds, mode=mode)
    filtered = await ExploreCitations(filtered_provider).execute(
        "W1", bounds, mode=mode, filters=ExplorationFilters(year_from=2020)
    )
    assert [str(node.paper.identifiers.openalex_id) for node in filtered.nodes] == ["W1", "W3"]
    assert not filtered.edges
    assert filtered_provider.calls == unfiltered_provider.calls
    assert filtered.requests == unfiltered.requests
    assert filtered.status == unfiltered.status == "complete"
    assert filtered.acquired_nodes == len(unfiltered.nodes) == 3
    assert filtered.acquired_edges == len(unfiltered.edges)
    assert {gap.work_id for gap in filtered.incomplete_metadata} <= {
        node.paper.identifiers.openalex_id for node in filtered.nodes
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing", "provider", "requests", "cancelled"])
async def test_filtered_partial_results_keep_diagnostics(failure: str) -> None:
    """Filter partial and cancelled graphs while preserving acquisition failures and bounds."""
    outcomes = {
        "provider": ProviderMalformedResponseError("fixture failure"),
        "cancelled": asyncio.CancelledError(),
    }
    records = {"W1": paper("W1", "W2", "W3"), "W2": rich_record("W2")}
    if failure in outcomes:
        records["W3"] = outcomes[failure]
    provider = Provider(records)
    bounds = ExplorationLimits(max_requests=2 if failure == "requests" else 100)
    try:
        result = await ExploreCitations(provider).execute(
            "W1", bounds, filters=ExplorationFilters(year_from=2020)
        )
    except ExplorationCancelled as exc:
        assert failure == "cancelled"
        result = exc.result
    reason = {
        "missing": "unresolved_references",
        "provider": "provider_failure",
        "requests": "requests",
        "cancelled": "cancelled",
    }[failure]
    assert result.stop_reasons == (reason,)
    assert result.status == ("failed" if failure in outcomes else "truncated")
    assert result.unresolved[-1].target == "W3"
    assert len(result.nodes) == 2
    assert len(result.edges) == 1
    assert result.acquired_edges == 2
    assert result.filters == ExplorationFilters(year_from=2020)
    assert all(
        edge.source in {node.paper.identifiers.openalex_id for node in result.nodes}
        and edge.target in {node.paper.identifiers.openalex_id for node in result.nodes}
        for edge in result.edges
    )


@pytest.mark.asyncio
async def test_filtering_at_elapsed_boundary_and_missing_seed() -> None:
    """Retain deadlines and missing-seed status even when filters would exclude every work."""
    clock = Clock()
    result = await ExploreCitations(
        Provider({"W1": paper("W1", "W2"), "W2": rich_record("W2")}, clock, 0.5), clock=clock
    ).execute("W1", ExplorationLimits(max_seconds=1), filters=ExplorationFilters(topic="Absent"))
    assert result.stop_reasons == ("elapsed_time",)
    assert len(result.nodes) == 1
    assert not result.edges
    missing = await ExploreCitations(Provider({})).execute("W9", filters=ExplorationFilters())
    assert missing.stop_reasons == ("seed_not_found",)
    assert missing.seed is None and not missing.nodes and not missing.edges


@pytest.mark.parametrize("mode", ["outgoing", "incoming", "both"])
def test_filter_and_evidence_journey(
    mode: ExplorationMode, capsys: pytest.CaptureFixture[str]
) -> None:
    """Select returned records and trace paper/edge evidence to fixtures across callers."""
    records = [
        paper("W1", "W2", "W4"),
        rich_record("W2", "W1"),
        rich_record("W3", "W1"),
        paper("W4", "W1"),
    ]
    values = {
        "year_from": 2020,
        "year_to": 2020,
        "min_citations": 0,
        "max_citations": 0,
        "author": "  ADA Lovelace ",
        "venue": "Journal of Tests",
        "topic": "Graph Theory",
    }
    graph = asyncio.run(
        ExploreCitations(CitationProvider(records)).execute(
            "W1", mode=mode, filters=ExplorationFilters(**values)
        )
    )
    library = json.loads(json.dumps(asdict(graph), default=_json_default))
    with TestClient(create_app(CitationProvider(records))) as client:
        response = client.post(
            "/v1/graphs/explore", json={"identifier": "W1", "mode": mode, "filters": values}
        )
        assert response.status_code == 200
        http = response.json()
        if mode == "outgoing":
            legacy = client.post(
                "/v1/graphs/outgoing", json={"identifier": "W1", "filters": values}
            )
            assert legacy.status_code == 200
            assert legacy.json()["nodes"] == library["nodes"]
    args = ["explore", "W1", "--mode", mode]
    for name, value in values.items():
        args.extend([f"--{name.replace('_', '-')}", str(value)])
    assert run(args, provider=CitationProvider(records)) == 0
    cli = json.loads(capsys.readouterr().out)
    for payload in (library, http, cli):
        payload.pop("elapsed_seconds")
    assert library == http == cli
    assert library["filters"]["author"] == "ada lovelace"
    assert library["filter_scope"] == "returned_results"
    fixtures = {str(record.paper.identifiers.openalex_id): record for record in records}
    returned = {
        node["paper"]["identifiers"]["openalex_id"]["value"]: node for node in http["nodes"]
    }
    for work, node in returned.items():
        assert node["paper"]["title"] == fixtures[work].paper.title
        assert Evidence.from_dict(node["evidence"]) == fixtures[work].evidence
        for topic in node["paper"]["topics"]:
            assert topic["inference_status"] == "inferred_provider"
            assert topic["score"] is None
    assert http["edges"]
    for edge in http["edges"]:
        source, target = edge["source"]["value"], edge["target"]["value"]
        assert source in returned and target in returned
        fixture = fixtures[source]
        assert edge["referenced_id"]["value"] in [
            str(ref) for ref in fixture.paper.referenced_works
        ]
        evidence = edge["evidence"]
        assert evidence["id"] == f"openalex:citation:{source}:{target}"
        assert evidence["provider"] == fixture.evidence.provider
        assert evidence["provider_record_id"] == fixture.evidence.provider_record_id
        assert evidence["source_url"] == fixture.evidence.source_url
        assert datetime.fromisoformat(evidence["observed_at"]) == fixture.evidence.observed_at
        assert evidence["inference_status"] == "reported"


@pytest.mark.parametrize(
    "filters",
    [
        {"year_from": True},
        {"year_from": "2020"},
        {"year_from": 2022, "year_to": 2020},
        {"topic": " "},
        {"unknown": "value"},
        {"author": ["Ada"]},
    ],
)
def test_invalid_http_filters_do_not_acquire(filters: dict[str, object]) -> None:
    """Reject malformed and semantically invalid inputs consistently on both routes."""
    provider = Provider({})
    with TestClient(create_app(provider)) as client:
        for route in ("outgoing", "explore"):
            response = client.post(
                f"/v1/graphs/{route}", json={"identifier": "W1", "filters": filters}
            )
            assert response.status_code == 422
    assert not provider.calls


def test_invalid_cli_filters_do_not_acquire(capsys: pytest.CaptureFixture[str]) -> None:
    """Return the documented input-error code before using the injected provider."""
    provider = Provider({})
    assert run(["explore", "W1", "--min-citations", "-1"], provider=provider) == 2
    assert not provider.calls
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "invalid_filters"


@pytest.mark.asyncio
async def test_empty_filters_and_merged_assertion() -> None:
    """Empty predicates retain metadata, remove unresolved edges and preserve merge evidence."""
    records = {"W1": paper("W1", "W2", "W4"), "W2": rich_record("W3")}
    unfiltered = await ExploreCitations(Provider(records)).execute("W1")
    filtered = await ExploreCitations(Provider(records)).execute("W1", filters=ExplorationFilters())
    assert filtered.nodes == unfiltered.nodes
    assert filtered.status == unfiltered.status == "truncated"
    assert filtered.unresolved == unfiltered.unresolved
    assert len(unfiltered.edges) == 2 and len(filtered.edges) == 1
    edge = filtered.edges[0]
    assert str(edge.target) == "W3" and str(edge.referenced_id) == "W2"
    assert edge.evidence.id == "openalex:citation:W1:W2"


def test_positive_count_and_year_extremes() -> None:
    """Accept valid year extremes and enforce both sides of positive citation counts."""
    record = replace(rich_record("W2").paper, cited_by_count=10)
    assert ExplorationFilters(year_from=1, year_to=9999).matches(record)
    assert ExplorationFilters(min_citations=10, max_citations=10).matches(record)
    assert not ExplorationFilters(max_citations=9).matches(record)
    assert not ExplorationFilters(min_citations=11).matches(record)


def test_filtered_truncation_transport_journey(capsys: pytest.CaptureFixture[str]) -> None:
    """A filtered seed-only response keeps truncated status and the CLI exit code."""
    records = {"W1": paper("W1", "W2"), "W2": rich_record("W2")}
    with TestClient(create_app(Provider(records))) as client:
        response = client.post(
            "/v1/graphs/explore",
            json={
                "identifier": "W1",
                "limits": {"max_requests": 1},
                "filters": {"year_from": 2020},
            },
        )
        assert response.status_code == 200
        http = response.json()
    assert (
        run(
            ["explore", "W1", "--max-requests", "1", "--year-from", "2020"],
            provider=Provider(records),
        )
        == 5
    )
    cli = json.loads(capsys.readouterr().out)
    for payload in (http, cli):
        payload.pop("elapsed_seconds")
    assert http == cli
    assert http["status"] == "truncated" and http["stop_reasons"] == ["requests"]
    assert len(http["nodes"]) == 1 and not http["edges"]


def test_normalized_filter_round_trip() -> None:
    """Normalized names remain valid input even when Unicode case folding expands text."""
    filters = ExplorationFilters(author="  Straße  ", topic="ß" * 150)
    assert filters.author == "strasse"
    assert ExplorationFilters(**asdict(filters)) == filters
    with pytest.raises(InvalidFilterError):
        ExplorationFilters(topic="ß" * 151)
    provider = Provider({})
    with TestClient(create_app(provider)) as client:
        response = client.post(
            "/v1/graphs/explore",
            json={"identifier": "W1", "filters": {"year_from": 2021, "year_to": 2020}},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_filters"
    assert not provider.calls
