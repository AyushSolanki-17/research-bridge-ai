"""Supported framework-independent paper acquisition contracts."""

from research_bridge.research.papers.application.acquisition import (
    AcquisitionBudget,
    AcquisitionLimitReached,
)
from research_bridge.research.papers.application.ports import PaperProviderPort, ResolvedPaper
from research_bridge.research.papers.application.resolve_paper import ResolvePaper
from research_bridge.research.papers.application.search_papers import (
    CandidatePage,
    InvalidSearchError,
    PaperSearchPort,
    SearchLimits,
    SearchPapers,
    SearchResult,
)

__all__ = [
    "CandidatePage",
    "InvalidSearchError",
    "PaperSearchPort",
    "SearchLimits",
    "SearchPapers",
    "SearchResult",
    "AcquisitionBudget",
    "AcquisitionLimitReached",
    "PaperProviderPort",
    "ResolvedPaper",
    "ResolvePaper",
]
