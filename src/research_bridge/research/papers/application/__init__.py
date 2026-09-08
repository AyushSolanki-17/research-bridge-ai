"""Supported framework-independent paper acquisition contracts."""

from research_bridge.research.papers.application.acquisition import (
    AcquisitionBudget,
    AcquisitionLimitReached,
)
from research_bridge.research.papers.application.ports import PaperProviderPort, ResolvedPaper
from research_bridge.research.papers.application.resolve_paper import ResolvePaper

__all__ = [
    "AcquisitionBudget",
    "AcquisitionLimitReached",
    "PaperProviderPort",
    "ResolvedPaper",
    "ResolvePaper",
]
