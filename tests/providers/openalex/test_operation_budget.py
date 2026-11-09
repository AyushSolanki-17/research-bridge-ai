"""Verify physical HTTP accounting inside graph acquisition budgets."""

from unittest.mock import AsyncMock

import httpx
import pytest

from research_bridge.core import ExplorationLimits, ExploreCitations, OpenAlexWorkId
from research_bridge.core.budget import AcquisitionBudget, AcquisitionLimitReached
from research_bridge.providers.openalex import OpenAlexProvider, OpenAlexSettings


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [301, 503])
async def test_redirects_and_retries_share_request_budget(
    status: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every physical request consumes the same operation allowance."""
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, headers={"Location": "/works/W2"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ExploreCitations(OpenAlexProvider(OpenAlexSettings(), client)).execute(
            "W1", ExplorationLimits(max_requests=2)
        )
    assert len(calls) == result.requests == 2
    assert result.stop_reasons == ("requests",)
    assert result.status == "truncated"


@pytest.mark.asyncio
async def test_backoff_cannot_outlive_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject retry waits exceeding remaining time without sleeping."""
    sleep = AsyncMock()
    monkeypatch.setattr("asyncio.sleep", sleep)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(503))
    ) as client:
        adapter = OpenAlexProvider(OpenAlexSettings(), client)
        with pytest.raises(AcquisitionLimitReached) as error:
            await adapter.fetch_paper(OpenAlexWorkId("W1"), budget=AcquisitionBudget(10, 0.1))
    assert error.value.reason == "elapsed_time"
    sleep.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "refs,complete",
    [([], True), (None, False), (["invalid"], False), (["https://openalex.org/W2"], True)],
)
async def test_reference_list_completeness(refs: object, complete: bool) -> None:
    """Do not confuse malformed or absent references with known empty lists."""
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"id": "https://openalex.org/W1", "referenced_works": refs}
            )
        )
    ) as client:
        result = await OpenAlexProvider(OpenAlexSettings(), client).fetch_paper(
            OpenAlexWorkId("W1")
        )
    assert result.paper.references_complete is complete
