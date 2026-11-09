"""Prove Research Bridge mounts cleanly inside a caller-owned FastAPI app."""

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from research_bridge import ResearchBridge
from research_bridge.api import create_router, install_error_handlers
from research_bridge.core import (
    AcquisitionBudget,
    Doi,
    Evidence,
    OpenAlexWorkId,
    Paper,
    PaperIdentifiers,
    ResolvedPaper,
)


class EmbeddedProvider:
    """Minimal caller-owned provider used by the embedding contract test."""

    async def fetch_paper(
        self,
        identifier: Doi | OpenAlexWorkId,
        *,
        budget: AcquisitionBudget | None = None,
    ) -> ResolvedPaper:
        """Return one canonical record without depending on FastAPI state."""
        if budget:
            budget.consume_request()
        work_id = OpenAlexWorkId("W1")
        return ResolvedPaper(
            Paper(PaperIdentifiers(work_id), title="Embedded paper", references_complete=True),
            Evidence(
                id="fixture:work:W1",
                provider="fixture",
                provider_record_id="W1",
                source_url="https://example.test/works/W1",
                observed_at=datetime(2026, 9, 21, tzinfo=UTC),
            ),
        )


def test_caller_owned_app_mounts_router_without_application_state() -> None:
    """Mount the router under a caller prefix and retain caller app ownership."""
    app = FastAPI(title="Consumer API")
    install_error_handlers(app)
    app.include_router(create_router(ResearchBridge(EmbeddedProvider()), prefix="/research"))

    with TestClient(app) as client:
        response = client.post("/research/papers/resolve", json={"identifier": "W1"})
        invalid = client.post("/research/papers/resolve", json={"identifier": "bad"})

    assert response.status_code == 200
    assert response.json()["paper"]["title"] == "Embedded paper"
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_identifier"
    assert vars(app.state)["_state"] == {}
