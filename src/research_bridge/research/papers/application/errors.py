"""Application-level errors for paper resolution."""

from __future__ import annotations


class PaperNotFoundError(LookupError):
    """The requested work does not exist in the provider."""

    def __init__(self, identifier: str) -> None:
        super().__init__(f"paper not found: {identifier}")
        self.identifier = identifier


class ProviderRateLimitedError(RuntimeError):
    """Provider signaled rate limiting (HTTP 429)."""


class ProviderTimeoutError(TimeoutError):
    """A bounded provider request timed out."""


class ProviderMalformedResponseError(ValueError):
    """Provider returned syntactically valid JSON that violates expected shape."""


class ProviderRetryExhaustedError(RuntimeError):
    """Retries were exhausted without success."""

    def __init__(self, message: str, *, attempts: int) -> None:
        super().__init__(message)
        self.attempts = attempts
