"""Stable errors raised by the framework-independent business API."""

from __future__ import annotations


class ResearchBridgeError(Exception):
    """Base class for expected business and provider failures."""


class InvalidInputError(ValueError, ResearchBridgeError):
    """Base class for invalid caller-supplied business input."""


class InvalidIdentifierError(InvalidInputError):
    """A raw identifier does not match a supported form."""

    def __init__(self, raw: str, reason: str) -> None:
        """Describe the rejected value without losing the validation reason."""
        super().__init__(f"invalid identifier {raw!r}: {reason}")
        self.raw = raw
        self.reason = reason


class InvalidSearchError(InvalidInputError):
    """The title query or requested candidate page is invalid."""


class InvalidFilterError(InvalidInputError):
    """A metadata predicate has an invalid type, range, or name."""


class InvalidLimitsError(InvalidInputError):
    """An operation limit is outside the supported range."""


class UnsupportedOperationError(ResearchBridgeError):
    """The configured provider does not support the requested operation."""


class PaperNotFoundError(LookupError, ResearchBridgeError):
    """The requested work does not exist in the provider."""

    def __init__(self, identifier: str) -> None:
        super().__init__(f"paper not found: {identifier}")
        self.identifier = identifier


class ProviderRateLimitedError(RuntimeError, ResearchBridgeError):
    """Provider signaled rate limiting (HTTP 429)."""


class ProviderTimeoutError(TimeoutError, ResearchBridgeError):
    """A bounded provider request timed out."""


class ProviderMalformedResponseError(ValueError, ResearchBridgeError):
    """Provider returned syntactically valid JSON that violates expected shape."""


class ProviderRetryExhaustedError(RuntimeError, ResearchBridgeError):
    """Retries were exhausted without success."""

    def __init__(self, message: str, *, attempts: int) -> None:
        super().__init__(message)
        self.attempts = attempts
