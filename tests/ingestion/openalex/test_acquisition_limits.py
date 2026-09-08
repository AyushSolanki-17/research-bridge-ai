"""Exercise acquisition limits and malformed metadata without network access."""

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from research_bridge.ingestion.openalex.infrastructure.openalex_adapter import (
    OpenAlexPaperAdapter,
    reconstruct_abstract,
)
from research_bridge.ingestion.openalex.infrastructure.settings import OpenAlexSettings
from research_bridge.research.papers.application.errors import (
    ProviderRateLimitedError,
    ProviderRetryExhaustedError,
)
from research_bridge.research.papers.domain.identifiers import OpenAlexWorkId


@pytest.mark.parametrize("timeout", [float("inf"), float("nan"), -1, 0, 61, True])
def test_invalid_timeout(timeout: float) -> None:
    """Reject timeout values outside the finite supported range."""
    with pytest.raises(ValueError):
        OpenAlexSettings(timeout_seconds=timeout)


@pytest.mark.parametrize("retries", [-1, 6, True])
def test_invalid_retry_count(retries: int) -> None:
    """Reject retry counts that violate the request limit."""
    with pytest.raises(ValueError):
        OpenAlexSettings(max_retries=retries)


def test_environment_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment settings use the same validation and hide credentials in repr."""
    monkeypatch.setenv("OPENALEX_TIMEOUT", "inf")
    with pytest.raises(ValueError):
        OpenAlexSettings.from_env()
    assert "secret-value" not in repr(OpenAlexSettings(api_key="secret-value"))


@pytest.mark.asyncio
@pytest.mark.parametrize("retry_after", ["60", "inf", "Wed, 01 Jan 2098 00:00:00 GMT"])
async def test_excessive_retry_after_stops(
    retry_after: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stop without sleeping or retrying earlier than the provider permits."""
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep)
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(429, headers={"Retry-After": retry_after})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAlexPaperAdapter(OpenAlexSettings(), client)
        with pytest.raises(ProviderRateLimitedError):
            await adapter.fetch_paper(OpenAlexWorkId("W1"))
    assert len(requests) == 1
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_delay_and_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Honor a short Retry-After and stop acquisition when backoff is cancelled."""
    sleep = AsyncMock(side_effect=asyncio.CancelledError)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(429, headers={"Retry-After": "1"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(asyncio.CancelledError):
            await OpenAlexPaperAdapter(OpenAlexSettings(), client).fetch_paper(OpenAlexWorkId("W1"))
    sleep.assert_awaited_once_with(1.0)
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [True, -1, "unknown", None])
async def test_malformed_optional_numbers(value: object) -> None:
    """Malformed counts and scores remain unknown rather than becoming facts."""
    payload = {
        "id": "https://openalex.org/W1",
        "cited_by_count": value,
        "topics": [{"score": value}],
    }
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    ) as client:
        result = await OpenAlexPaperAdapter(OpenAlexSettings(), client).fetch_paper(
            OpenAlexWorkId("W1")
        )
    assert result.paper.cited_by_count is None
    assert result.paper.topics[0].score is None
    assert reconstruct_abstract({"word": [True]}) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "network", "rate_limit", "server"])
@pytest.mark.parametrize("recover", [False, True])
async def test_retry_outcomes(failure: str, recover: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    """Recover from transient failures or exhaust exactly the configured attempts."""
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep)
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if recover and len(requests) == 2:
            return httpx.Response(200, json={"id": "https://openalex.org/W1"})
        if failure == "timeout":
            raise httpx.ReadTimeout("offline timeout", request=request)
        if failure == "network":
            raise httpx.ConnectError("offline failure", request=request)
        return httpx.Response(429 if failure == "rate_limit" else 503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAlexPaperAdapter(OpenAlexSettings(max_retries=1), client)
        if recover:
            result = await adapter.fetch_paper(OpenAlexWorkId("W1"))
            assert result.evidence.provider_record_id == "W1"
        else:
            with pytest.raises(ProviderRetryExhaustedError) as error:
                await adapter.fetch_paper(OpenAlexWorkId("W1"))
            assert error.value.attempts == 2
            assert error.value.__cause__ is not None
    assert len(requests) == 2
    sleep.assert_awaited_once_with(0.2)
