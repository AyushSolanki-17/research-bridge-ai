"""Central HTTP translation for expected input and paper acquisition failures."""

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from research_bridge.core import (
    InvalidFilterError,
    InvalidIdentifierError,
    InvalidLimitsError,
    InvalidSearchError,
    PaperNotFoundError,
    ProviderMalformedResponseError,
    ProviderRateLimitedError,
    ProviderRetryExhaustedError,
    ProviderTimeoutError,
    UnsupportedOperationError,
)


class ErrorDetail(BaseModel):
    """Stable error code and safe message, without internal exception details."""

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Expected research HTTP failure envelope."""

    error: ErrorDetail


ERRORS: dict[type[Exception], tuple[int, str, str]] = {
    InvalidIdentifierError: (422, "invalid_identifier", "Unsupported or malformed identifier."),
    InvalidSearchError: (422, "invalid_search", "Invalid title query or candidate page."),
    InvalidFilterError: (422, "invalid_filters", "Invalid metadata filter values."),
    InvalidLimitsError: (422, "invalid_limits", "Limits are outside the supported range."),
    PaperNotFoundError: (404, "not_found", "Paper not found."),
    ProviderRateLimitedError: (429, "rate_limited", "Provider rate limit reached."),
    ProviderTimeoutError: (504, "provider_timeout", "Provider request timed out."),
    ProviderMalformedResponseError: (502, "malformed_response", "Provider response is invalid."),
    ProviderRetryExhaustedError: (502, "retries_exhausted", "Provider retries exhausted."),
    UnsupportedOperationError: (501, "unsupported_operation", "Operation is not configured."),
}


async def research_error(request: Request, exc: Exception) -> JSONResponse:
    """Translate known failures without exposing upstream URLs or exception messages."""
    status, code, message = ERRORS[type(exc)]
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


async def invalid_request(request: Request, exc: Exception) -> JSONResponse:
    """Reject malformed HTTP input with the documented safe error envelope."""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "invalid_request",
                "message": "Request fields have invalid types or shape.",
            }
        },
    )
