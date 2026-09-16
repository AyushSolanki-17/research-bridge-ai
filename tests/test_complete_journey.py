"""Complete HTTP journeys using real provider translation and inspectable fixtures."""

import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from research_bridge.api.app import create_app
from research_bridge.knowledge_graph.application import (
    ExplorationFilters,
    ExplorationLimits,
    ExploreCitations,
)
from tests.offline_journey import (
    TITLE,
    adapter,
    inspect_graph,
    json_value,
    provider_server,
    stable,
    verify_library_cli,
)


@pytest.fixture(scope="module")
def provider_url() -> Iterator[str]:
    """Share a stateless synthetic HTTP server across complete HTTP journeys."""
    with provider_server() as base_url:
        yield base_url


def test_library_and_installed_cli_journey() -> None:
    """Run the same standalone verification used for clean package installations."""
    verify_library_cli()


@pytest.mark.parametrize("mode", ["outgoing", "incoming", "both"])
@pytest.mark.parametrize("depth", [1, 2, 3])
def test_search_selection_graph_inspection(provider_url: str, mode: str, depth: int) -> None:
    """Review ambiguous paginated titles and explicitly explore the second candidate."""
    provider = adapter(provider_url)
    with TestClient(create_app(provider, search_provider=provider)) as client:
        first = client.post("/v1/papers/search", json={"query": TITLE, "limits": {"page_size": 1}})
        assert first.status_code == 200 and first.json()["status"] == "more"
        second = client.post(
            "/v1/papers/search",
            json={"query": TITLE, "limits": {"page_size": 1}, "page": first.json()["next_page"]},
        )
        assert second.status_code == 200 and second.json()["status"] == "complete"
        assert second.json()["next_page"] is None and second.json()["requests"] == 2
        candidate = second.json()["candidates"][0]
        other = first.json()["candidates"][0]
        assert candidate["paper"]["title"] == other["paper"]["title"] == TITLE
        assert candidate["paper"]["authors"] != other["paper"]["authors"]
        selected = candidate["paper"]["identifiers"]["openalex_id"]["value"]
        assert selected == "W10"
        request = {
            "identifier": selected,
            "mode": mode,
            "limits": {"depth": depth},
            "filters": {"year_from": 2020, "topic": "Graph Theory"},
        }
        response = client.post("/v1/graphs/explore", json=request)
        assert response.status_code == 200
        graph = response.json()
        inspect_graph(graph, mode, depth)
        assert graph["nodes"][0]["evidence"]["id"] == candidate["evidence"]["id"]
        library = asyncio.run(
            ExploreCitations(provider).execute(
                selected,
                ExplorationLimits(depth=depth),
                mode=mode,
                filters=ExplorationFilters(year_from=2020, topic="Graph Theory"),
            )
        )
        assert stable(graph) == stable(json_value(library))
        resolved = client.post("/v1/papers/resolve", json={"identifier": "doi:10.1234/W10"})
        assert resolved.status_code == 200
        assert stable(resolved.json()) == stable(candidate)
        request["identifier"] = "doi:10.1234/W10"
        alternative = client.post("/v1/graphs/explore", json=request)
        assert alternative.status_code == 200
        assert stable(alternative.json()) == stable(graph)


def test_http_incomplete_acquisition(provider_url: str) -> None:
    """Budget and unresolved-reference diagnostics survive result filtering."""
    with TestClient(create_app(adapter(provider_url))) as client:
        limited = client.post(
            "/v1/graphs/explore",
            json={
                "identifier": "W10",
                "mode": "both",
                "limits": {"max_requests": 1},
                "filters": {},
            },
        )
        assert limited.status_code == 200
        assert limited.json()["status"] == "truncated"
        assert limited.json()["stop_reasons"] == ["requests"]
        assert limited.json()["requests"] == 1
        assert len(limited.json()["nodes"]) == 1 and not limited.json()["edges"]
        missing = client.post("/v1/graphs/explore", json={"identifier": "W30", "filters": {}})
        assert missing.status_code == 200 and missing.json()["status"] == "truncated"
        assert missing.json()["stop_reasons"] == ["unresolved_references"]
        assert missing.json()["unresolved"][0]["target"] == "W404"
        assert missing.json()["acquired_edges"] == 2 and len(missing.json()["edges"]) == 1


def test_http_failure_after_incoming_page() -> None:
    """An actual upstream HTTP failure retains acquired papers and their evidence."""
    with provider_server(fail_incoming=True) as base_url:
        with TestClient(create_app(adapter(base_url))) as client:
            response = client.post(
                "/v1/graphs/explore", json={"identifier": "W10", "mode": "incoming", "filters": {}}
            )
    assert response.status_code == 502
    graph = response.json()
    assert graph["status"] == "failed" and graph["stop_reasons"] == ["provider_failure"]
    assert {node["paper"]["identifiers"]["openalex_id"]["value"] for node in graph["nodes"]} == {
        "W10",
        "W20",
    }
    assert graph["edges"][0]["evidence"]["id"] == "openalex:citation:W20:W10"
    assert graph["unread_incoming_pages"][0]["cursor"] == "unread"
