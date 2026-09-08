"""Operation-scoped acquisition accounting shared by provider consumers."""

import math
import time
from collections.abc import Callable


class AcquisitionLimitReached(RuntimeError):
    """Acquisition stopped at a request or elapsed-time limit.

    Attributes:
        reason: Machine-readable limit name.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AcquisitionBudget:
    """Mutable request accounting for one operation, never shared across callers.

    Each physical request, including retries and redirects, consumes one unit.
    The monotonic clock can be injected for deterministic boundary tests.
    """

    def __init__(
        self, max_requests: int, max_seconds: float, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        """Start accounting with validated positive limits.

        Args:
            max_requests: Maximum physical requests across the operation.
            max_seconds: Maximum elapsed time across all acquisition and processing.
            clock: Monotonic seconds source.

        Raises:
            ValueError: If limits are invalid.
        """
        if type(max_requests) is not int or max_requests < 1:
            raise ValueError("max_requests must be a positive integer")
        if isinstance(max_seconds, bool) or not math.isfinite(max_seconds) or max_seconds <= 0:
            raise ValueError("max_seconds must be finite and positive")
        self._max_requests = max_requests
        self._max_seconds = max_seconds
        self._clock = clock
        self._started = clock()
        self._requests = 0

    @property
    def requests(self) -> int:
        """Number of physical requests already started."""
        return self._requests

    @property
    def elapsed(self) -> float:
        """Elapsed monotonic seconds since operation start."""
        return max(0.0, self._clock() - self._started)

    def remaining_seconds(self) -> float:
        """Return remaining time or raise AcquisitionLimitReached at the deadline."""
        remaining = self._max_seconds - self.elapsed
        if remaining <= 0:
            raise AcquisitionLimitReached("elapsed_time")
        return remaining

    def consume_request(self) -> None:
        """Reserve one physical request or raise AcquisitionLimitReached."""
        self.remaining_seconds()
        if self._requests >= self._max_requests:
            raise AcquisitionLimitReached("requests")
        self._requests += 1

    def check_wait(self, seconds: float) -> None:
        """Reject a wait that cannot finish before the operation deadline."""
        if seconds >= self.remaining_seconds():
            raise AcquisitionLimitReached("elapsed_time")
