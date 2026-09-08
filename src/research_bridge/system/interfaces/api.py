"""Process health transport; no research or data-readiness claim."""

from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@dataclass(frozen=True)
class HealthResponse:
    """Immutable HTTP contract for process liveness."""

    status: Literal["ok"] = "ok"


@router.get("/health", response_model=HealthResponse, operation_id="get_health")
def health() -> HealthResponse:
    """Report process availability without checking databases or external providers."""
    return HealthResponse()
