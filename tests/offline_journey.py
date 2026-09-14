"""Reproduce library and installed CLI journeys against a synthetic local provider.

Run this file with the clean environment's Python and ``--require-core-only`` to
verify installation without importing tests, the checkout's source or FastAPI.
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.util import find_spec
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, unquote, urlsplit

from research_bridge.ingestion.openalex.infrastructure.openalex_adapter import OpenAlexPaperAdapter
from research_bridge.ingestion.openalex.infrastructure.settings import OpenAlexSettings
from research_bridge.knowledge_graph.application import (
    ExplorationFilters,
    ExplorationLimits,
    ExploreCitations,
    ExploreOutgoing,
)
from research_bridge.research.papers.application import ResolvePaper, SearchLimits, SearchPapers

TITLE = "Synthetic citation methods"
REFERENCES = {
    "W99": [],
    "W10": ["W11"],
    "W11": ["W12"],
    "W12": ["W13"],
    "W13": [],
    "W20": ["W10"],
    "W21": ["W20"],
    "W22": ["W21"],
    "W30": ["W31", "W404"],
    "W31": [],
}


def payload(work: str) -> dict:
    """Return original fixture metadata and reference assertions for one work.

    Args:
        work: Identifier in REFERENCES.

    Returns:
        Synthetic OpenAlex response, including one excluded intermediate paper.
    """
    return {
        "id": f"https://openalex.org/{work}",
        "doi": f"https://doi.org/10.1234/{work.lower()}",
        "title": TITLE if work in ("W99", "W10") else f"Synthetic {work}",
        "publication_date": "2010-01-01" if work == "W11" else "2020-01-01",
        "authorships": [{"author": {"display_name": f"Author {work}"}}],
        "primary_location": {"source": {"id": "S1", "display_name": "Fixture Journal"}},
        "cited_by_count": 0,
        "topics": [{"id": "T1", "display_name": "Graph Theory", "score": None}],
        "referenced_works": [f"https://openalex.org/{item}" for item in REFERENCES[work]],
    }


@contextmanager
def provider_server(*, fail_incoming: bool = False) -> Iterator[str]:
    """Serve bounded synthetic HTTP pages on an ephemeral loopback port.

    Args:
        fail_incoming: Fail the second incoming page after returning one citing work.

    Yields:
        Local provider URL. The server and its thread close on exit.
    """

    class Handler(BaseHTTPRequestHandler):
        """Translate only fixture lookup, title search and incoming page requests."""

        def do_GET(self) -> None:
            """Serve fixture JSON; unexpected identifiers return a real HTTP 404."""
            url = urlsplit(self.path)
            query = parse_qs(url.query)
            status = 200
            body = {}
            if url.path == "/works":
                operation = query.get("filter", [""])[0]
                cursor = query.get("cursor", ["*"])[0]
                if operation == f"title.search:{TITLE}":
                    works, following = (["W99"], "selected") if cursor == "*" else (["W10"], None)
                elif operation.startswith("cites:"):
                    target = operation.removeprefix("cites:")
                    works = [work for work, refs in REFERENCES.items() if target in refs]
                    following = "unread" if target == "W10" and cursor == "*" else None
                    if cursor != "*":
                        works = []
                        if fail_incoming and target == "W10":
                            status = 503
                else:
                    status, works, following = 400, [], None
                body = {
                    "results": [payload(work) for work in works],
                    "meta": {"next_cursor": following},
                }
            else:
                work = unquote(url.path.removeprefix("/works/")).split("/")[-1].upper()
                if work in REFERENCES:
                    body = payload(work)
                else:
                    status = 404
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: object) -> None:
            """Keep synthetic HTTP requests out of test and CLI output."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def adapter(base_url: str) -> OpenAlexPaperAdapter:
    """Compose the real adapter with local acquisition and no retry delay.

    Args:
        base_url: Synthetic provider URL.

    Returns:
        Adapter with explicit settings, independent of environment credentials.
    """
    return OpenAlexPaperAdapter(OpenAlexSettings(base_url=base_url, max_retries=0))


def json_value(value: object) -> dict:
    """Serialize library dataclasses independently of either production transport.

    Args:
        value: Application result dataclass containing metadata and evidence.

    Returns:
        JSON-compatible mapping with ISO dates and observation timestamps.
    """

    def encode(item: object) -> str:
        if isinstance(item, date | datetime):
            return item.isoformat()
        raise TypeError(f"Unexpected serialized value: {type(item)}")

    return json.loads(json.dumps(asdict(value), default=encode))


def stable(value: object) -> object:
    """Compare records across observations after validating variable time fields.

    Args:
        value: Parsed JSON result or one of its nested values.

    Returns:
        Copy without observation timestamps and elapsed durations. All other fields
        remain available for exact comparison.
    """
    if isinstance(value, dict):
        if "observed_at" in value:
            assert datetime.fromisoformat(value["observed_at"]).utcoffset() is not None
        if "elapsed_seconds" in value:
            assert 0 <= value["elapsed_seconds"] <= 30
        return {
            key: stable(item)
            for key, item in value.items()
            if key not in ("observed_at", "elapsed_seconds")
        }
    if isinstance(value, list):
        return [stable(item) for item in value]
    return value


def cli(base_url: str, args: list[str], expected_exit: int = 0) -> dict:
    """Execute the installed console entrypoint with isolated provider settings.

    Args:
        base_url: Synthetic server URL.
        args: CLI arguments.
        expected_exit: Required process exit status.

    Returns:
        Parsed JSON from stdout; stderr must remain empty.
    """
    env = {key: value for key, value in os.environ.items() if not key.startswith("OPENALEX_")}
    env.update(OPENALEX_BASE_URL=base_url, OPENALEX_MAX_RETRIES="0", NO_PROXY="127.0.0.1")
    result = subprocess.run(
        [str(Path(sys.executable).parent / "research-bridge"), *args],
        env=env,
        cwd=Path(sys.executable).parent,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == expected_exit, result.stderr or result.stdout
    assert not result.stderr, result.stderr
    return json.loads(result.stdout)


def inspect_graph(graph: dict, mode: str, depth: int) -> None:
    """Check explicit depth membership, filtering and fixture-backed citation evidence.

    Args:
        graph: Serialized graph after applying the journey's year/topic filters.
        mode: Requested traversal direction.
        depth: Requested discovery hops, from one through three.

    Raises:
        AssertionError: Membership, metadata or source assertions differ from fixtures.
    """
    expected = {"W10"}
    if mode in ("outgoing", "both"):
        expected.update(["W11", "W12", "W13"][:depth])
    if mode in ("incoming", "both"):
        expected.update(["W20", "W21", "W22"][:depth])
    assert graph["status"] == "complete" and not graph["stop_reasons"]
    assert graph["acquired_nodes"] == len(expected)
    expected.discard("W11")
    nodes = {node["paper"]["identifiers"]["openalex_id"]["value"]: node for node in graph["nodes"]}
    assert set(nodes) == expected
    expected_edges = {
        (source, target)
        for source in expected
        for target in REFERENCES[source]
        if target in expected
    }
    assert {
        (edge["source"]["value"], edge["target"]["value"]) for edge in graph["edges"]
    } == expected_edges
    for work, node in nodes.items():
        assert node["paper"]["title"] == payload(work)["title"]
        assert node["paper"]["cited_by_count"] == 0
        assert node["evidence"]["id"] == f"openalex:work:{work}"
        assert node["evidence"]["provider_record_id"] == work
        assert node["evidence"]["source_url"] == payload(work)["id"]
    for edge in graph["edges"]:
        source, target = edge["source"]["value"], edge["target"]["value"]
        assert edge["referenced_id"]["value"] == target
        assert f"https://openalex.org/{target}" in payload(source)["referenced_works"]
        evidence = edge["evidence"]
        assert evidence["id"] == f"openalex:citation:{source}:{target}"
        assert evidence["provider_record_id"] == source
        assert evidence["source_url"] == payload(source)["id"]
        assert evidence["provider"] == "openalex" and evidence["inference_status"] == "reported"
    stable(graph)


def verify_library_cli() -> None:
    """Verify paginated explicit selection, every mode/depth and partial outcomes.

    Raises:
        AssertionError: A library or installed CLI contract differs from the fixture.
    """
    with provider_server() as base_url:
        provider = adapter(base_url)
        searcher = SearchPapers(provider)
        for page, work, status in [(1, "W99", "more"), (2, "W10", "complete")]:
            result = asyncio.run(searcher.execute(TITLE, SearchLimits(page_size=1), page=page))
            output = cli(base_url, ["search", TITLE, "--page-size", "1", "--page", str(page)])
            assert stable(output) == stable(json_value(result))
            assert output["status"] == status
            assert output["candidates"][0]["paper"]["identifiers"]["openalex_id"]["value"] == work
        selected = output["candidates"][0]["paper"]["identifiers"]["openalex_id"]["value"]
        resolved = asyncio.run(ResolvePaper(provider).execute("doi:10.1234/W10"))
        assert resolved.evidence.id == output["candidates"][0]["evidence"]["id"]
        assert stable(cli(base_url, ["resolve", "doi:10.1234/W10"])) == stable(json_value(resolved))
        for mode in ("outgoing", "incoming", "both"):
            for depth in (1, 2, 3):
                graph = asyncio.run(
                    ExploreCitations(provider).execute(
                        selected,
                        ExplorationLimits(depth=depth),
                        mode=mode,
                        filters=ExplorationFilters(year_from=2020, topic="Graph Theory"),
                    )
                )
                output = cli(
                    base_url,
                    [
                        "explore",
                        selected,
                        "--mode",
                        mode,
                        "--depth",
                        str(depth),
                        "--year-from",
                        "2020",
                        "--topic",
                        "Graph Theory",
                    ],
                )
                inspect_graph(output, mode, depth)
                assert stable(output) == stable(json_value(graph))
        limited = asyncio.run(
            ExploreCitations(provider).execute(
                selected,
                ExplorationLimits(max_requests=1),
                mode="both",
                filters=ExplorationFilters(),
            )
        )
        output = cli(base_url, ["explore", selected, "--mode", "both", "--max-requests", "1"], 5)
        assert output["status"] == limited.status == "truncated"
        assert output["stop_reasons"] == list(limited.stop_reasons) == ["requests"]
        assert output["requests"] == limited.requests == 1
        missing = asyncio.run(ExploreOutgoing(provider).execute("W30"))
        output = cli(base_url, ["explore", "W30"], 5)
        assert stable(output) == stable(json_value(missing))
        assert output["stop_reasons"] == ["unresolved_references"]
        assert output["unresolved"][0]["target"] == "W404"
    with provider_server(fail_incoming=True) as base_url:
        graph = asyncio.run(ExploreCitations(adapter(base_url)).execute("W10", mode="incoming"))
        output = cli(base_url, ["explore", "W10", "--mode", "incoming"], 4)
        assert stable(output) == stable(json_value(graph))
        assert output["status"] == "failed" and output["stop_reasons"] == ["provider_failure"]
        assert len(output["nodes"]) == 2 and len(output["edges"]) == 1
        assert output["unread_incoming_pages"][0]["cursor"] == "unread"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-core-only", action="store_true")
    options = parser.parse_args()
    if options.require_core_only:
        for module in ("fastapi", "starlette", "uvicorn", "pytest"):
            assert find_spec(module) is None, f"Unexpected optional dependency: {module}"
        import research_bridge

        assert Path(research_bridge.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    verify_library_cli()
    print(
        "Offline library/CLI journey passed: search, selection, all modes/depths, "
        "evidence and failures."
    )
