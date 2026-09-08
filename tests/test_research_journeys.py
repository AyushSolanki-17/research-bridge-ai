"""Library, HTTP and CLI journeys through the same deterministic provider."""

import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from research_bridge.api.app import create_app
from research_bridge.cli import run
from research_bridge.knowledge_graph.application import ExplorationLimits, ExploreOutgoing
from research_bridge.provenance.domain.evidence import Evidence
from research_bridge.research.papers.application import (
    AcquisitionBudget,
    ResolvedPaper,
    ResolvePaper,
)
from research_bridge.research.papers.application.errors import (
    PaperNotFoundError,
    ProviderMalformedResponseError,
    ProviderRateLimitedError,
    ProviderRetryExhaustedError,
    ProviderTimeoutError,
)
from research_bridge.research.papers.domain.identifiers import Doi, OpenAlexWorkId
from research_bridge.research.papers.domain.paper import Author, Paper, PaperIdentifiers


class FixtureProvider:
    """Deterministic provider shared by each transport and library invocation."""

    def __init__(self, failure: BaseException | None = None, failure_at: str | None = None) -> None:
        self.failure = failure
        self.failure_at = failure_at
        self.calls: list[str] = []

    async def fetch_paper(
        self, identifier: Doi | OpenAlexWorkId, *, budget: AcquisitionBudget | None = None
    ) -> ResolvedPaper:
        """Return synthetic metadata, consuming one physical request when budgeted."""
        if budget:
            budget.consume_request()
        raw = str(identifier)
        self.calls.append(raw)
        if self.failure and (self.failure_at is None or self.failure_at == raw):
            raise self.failure
        if raw not in ("W1", "W2", "10.1234/example"):
            raise PaperNotFoundError(raw)
        work = "W2" if raw == "W2" else "W1"
        return ResolvedPaper(
            Paper(
                PaperIdentifiers(OpenAlexWorkId(work), Doi("10.1234/example")),
                title=f"Synthetic {work}",
                authors=(Author("Example Author"),),
                cited_by_count=0,
                references_complete=True,
                referenced_works=(OpenAlexWorkId("W2"),) if work == "W1" else (),
            ),
            Evidence.paper_evidence(work, observed_at=datetime(2026, 9, 8, tzinfo=UTC)),
        )


def test_resolution_across_library_http_cli(capsys: pytest.CaptureFixture[str]) -> None:
    """All callers receive the same canonical metadata and stable evidence."""
    provider = FixtureProvider()
    record = asyncio.run(ResolvePaper(provider).execute("doi:10.1234/EXAMPLE"))
    with TestClient(create_app(provider)) as client:
        response = client.post("/v1/papers/resolve", json={"identifier": "doi:10.1234/EXAMPLE"})
    assert response.status_code == 200
    assert run(["resolve", "doi:10.1234/EXAMPLE"], provider=provider) == 0
    output = json.loads(capsys.readouterr().out)
    assert output == response.json()
    assert output["evidence"]["id"] == record.evidence.id
    assert output["paper"]["cited_by_count"] == 0
    assert provider.calls == ["10.1234/example"] * 3


@pytest.mark.parametrize("max_nodes,status,exit_code", [(2, "complete", 0), (1, "truncated", 5)])
def test_exploration_across_library_http_cli(
    max_nodes: int, status: str, exit_code: int, capsys: pytest.CaptureFixture[str]
) -> None:
    """Success and truncation preserve the same graph and source evidence in every caller."""
    provider = FixtureProvider()
    graph = asyncio.run(
        ExploreOutgoing(provider).execute("W1", ExplorationLimits(max_nodes=max_nodes))
    )
    with TestClient(create_app(provider)) as client:
        response = client.post(
            "/v1/graphs/outgoing", json={"identifier": "W1", "limits": {"max_nodes": max_nodes}}
        )
    assert response.status_code == 200
    assert run(["explore", "W1", "--max-nodes", str(max_nodes)], provider=provider) == exit_code
    output = json.loads(capsys.readouterr().out)
    http_result = response.json()
    output.pop("elapsed_seconds")
    http_result.pop("elapsed_seconds")
    assert output == http_result
    assert output["status"] == graph.status == status
    assert output["limits"] == asdict(graph.limits)
    if graph.edges:
        edge = output["edges"][0]
        assert edge["source"]["value"] == "W1"
        assert edge["target"]["value"] == "W2"
        assert edge["evidence"]["provider_record_id"] == "W1"
        assert edge["evidence"]["source_url"] == output["nodes"][0]["evidence"]["source_url"]


@pytest.mark.parametrize(
    "failure,status,code,exit_code",
    [
        (PaperNotFoundError("private"), 404, "not_found", 3),
        (ProviderRateLimitedError("private"), 429, "rate_limited", 4),
        (ProviderTimeoutError("private"), 504, "provider_timeout", 4),
        (ProviderMalformedResponseError("private"), 502, "malformed_response", 4),
        (ProviderRetryExhaustedError("private", attempts=2), 502, "retries_exhausted", 4),
    ],
)
def test_resolution_error_mapping(
    failure: Exception, status: int, code: str, exit_code: int, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both transports expose stable safe errors without internal exception messages."""
    provider = FixtureProvider(failure)
    with TestClient(create_app(provider)) as client:
        response = client.post("/v1/papers/resolve", json={"identifier": "W1"})
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "private" not in response.text
    assert run(["resolve", "W1"], provider=provider) == exit_code
    assert json.loads(capsys.readouterr().err) == response.json()


@pytest.mark.parametrize(
    "body",
    [
        {"identifier": "W1", "limits": {"depth": 4}},
        {"identifier": "W1", "limits": {"depth": True}},
        {"identifier": "W1", "limits": {"max_seconds": 0}},
        {"identifier": "W1", "limits": {"unknown": 1}},
        {"identifier": "W1", "unexpected": "field"},
        {"identifier": "invalid"},
        {"identifier": "x" * 2049},
        {},
    ],
)
def test_http_validation_before_acquisition(body: dict) -> None:
    """Reject invalid identifiers, shapes and budgets before provider work."""
    provider = FixtureProvider()
    with TestClient(create_app(provider)) as client:
        response = client.post("/v1/graphs/outgoing", json=body)
    assert response.status_code == 422
    assert "code" in response.json()["error"]
    assert provider.calls == []


def test_cli_invalid_inputs(capsys: pytest.CaptureFixture[str]) -> None:
    """CLI rejects invalid identifiers and limits before provider work."""
    provider = FixtureProvider()
    assert run(["resolve", "invalid"], provider=provider) == 2
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "invalid_identifier"
    assert run(["explore", "W1", "--depth", "4"], provider=provider) == 2
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "invalid_configuration"
    assert provider.calls == []


@pytest.mark.parametrize("missing,status,exit_code", [(True, 404, 3), (False, 502, 4)])
def test_failed_graphs_remain_inspectable(
    missing: bool, status: int, exit_code: int, capsys: pytest.CaptureFixture[str]
) -> None:
    """Missing seeds and upstream failures retain explicit failed graph contracts."""
    provider = FixtureProvider(
        PaperNotFoundError("W1") if missing else ProviderMalformedResponseError("private")
    )
    with TestClient(create_app(provider)) as client:
        response = client.post("/v1/graphs/outgoing", json={"identifier": "W1"})
    assert response.status_code == status
    assert response.json()["status"] == "failed"
    assert run(["explore", "W1"], provider=provider) == exit_code
    assert json.loads(capsys.readouterr().out)["stop_reasons"] == response.json()["stop_reasons"]


def test_documented_schema_contracts() -> None:
    """Versioned routes publish typed success, validation and partial-failure schemas."""
    schema = create_app(FixtureProvider()).openapi()
    assert schema["paths"]["/v1/papers/resolve"]["post"]["operationId"] == "resolve_paper"
    responses = schema["paths"]["/v1/graphs/outgoing"]["post"]["responses"]
    assert responses["502"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "ExplorationResult"
    )
    assert responses["422"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "ErrorResponse"
    )


def test_partial_failure_and_cli_cancellation(capsys: pytest.CaptureFixture[str]) -> None:
    """Failed acquisition and cancellation retain the seed and asserted edge."""
    provider = FixtureProvider(ProviderMalformedResponseError("private"), failure_at="W2")
    with TestClient(create_app(provider)) as client:
        response = client.post("/v1/graphs/outgoing", json={"identifier": "W1"})
    assert response.status_code == 502
    assert len(response.json()["nodes"]) == 1
    assert len(response.json()["edges"]) == 1
    assert response.json()["unresolved"][0]["target"] == "W2"
    assert run(["explore", "W1"], provider=provider) == 4
    output = json.loads(capsys.readouterr().out)
    assert output["nodes"] == response.json()["nodes"]
    assert output["edges"] == response.json()["edges"]
    cancelled = FixtureProvider(asyncio.CancelledError(), failure_at="W2")
    assert run(["explore", "W1"], provider=cancelled) == 130
    output = json.loads(capsys.readouterr().out)
    assert output["stop_reasons"] == ["cancelled"]
    assert len(output["nodes"]) == 1


def test_cli_help_and_version(capsys: pytest.CaptureFixture[str]) -> None:
    """Help and version commands remain usable without acquiring a provider record."""
    provider = FixtureProvider()
    assert run([], provider=provider) == 0
    assert "resolve" in capsys.readouterr().out
    with pytest.raises(SystemExit) as error:
        run(["--version"], provider=provider)
    assert error.value.code == 0
    assert provider.calls == []
