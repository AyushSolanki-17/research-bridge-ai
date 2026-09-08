"""OpenAlex provider settings via environment.

OpenAlex is free for casual use without a key. A free API key raises
daily budgets 10x. Keys can be sent as ``api_key`` query param or
``Authorization: Bearer`` header.

Access requirements (checked 2026-09-08 from
https://help.openalex.org/api/authentication/ and
https://help.openalex.org/api/get-single-entities/):
  - No authentication required for basic queries.
  - Free API key available at https://openalex.org/settings/api.
  - Send via ``?api_key=YOUR_KEY`` or ``Authorization: Bearer YOUR_KEY``.
  - Rate limits: 100 requests/second, daily budget; 429 on limit.
  - Data is provided under CC0 where applicable; respect OpenAlex
    attribution and terms. See https://openalex.org/ and provider docs.

Credentials are read from ``OPENALEX_API_KEY`` and never logged.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class OpenAlexSettings:
    """Provider configuration loaded from environment.

    Attributes:
        base_url: API base URL.
        api_key: Optional API key, or ``None`` when unauthenticated.
        timeout_seconds: Per-request timeout.
        max_retries: Finite retry limit for transient failures.
    """

    base_url: str = "https://api.openalex.org"
    api_key: str | None = field(default=None, repr=False)
    timeout_seconds: float = 10.0
    max_retries: int = 3

    def __post_init__(self) -> None:
        """Reject settings that defeat finite acquisition limits."""
        if (
            isinstance(self.timeout_seconds, bool)
            or not math.isfinite(self.timeout_seconds)
            or not 0 < self.timeout_seconds <= 60
        ):
            raise ValueError("timeout_seconds must be finite and in (0, 60]")
        if type(self.max_retries) is not int or not 0 <= self.max_retries <= 5:
            raise ValueError("max_retries must be an integer in [0, 5]")

    @classmethod
    def from_env(cls) -> OpenAlexSettings:
        """Load settings from environment variables.

        Environment:
            ``OPENALEX_API_KEY``: optional key.
            ``OPENALEX_BASE_URL``: optional override.
            ``OPENALEX_TIMEOUT``: optional timeout seconds.
            ``OPENALEX_MAX_RETRIES``: optional retry count.

        Returns:
            Populated :class:`OpenAlexSettings`.

        Raises:
            ValueError: If a configured timeout or retry count is invalid.
        """
        api_key = os.getenv("OPENALEX_API_KEY")
        base_url = os.getenv("OPENALEX_BASE_URL", "https://api.openalex.org")
        timeout_raw = os.getenv("OPENALEX_TIMEOUT", "10.0")
        retries_raw = os.getenv("OPENALEX_MAX_RETRIES", "3")
        timeout = float(timeout_raw)
        retries = int(retries_raw)
        return cls(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            timeout_seconds=timeout,
            max_retries=retries,
        )
