"""Public, framework-independent Research Bridge business API."""

from research_bridge.bridge import ResearchBridge
from research_bridge.core import (
    ExplorationFilters,
    ExplorationLimits,
    ExplorationMode,
    ExplorationResult,
    ResolvedPaper,
    SearchLimits,
    SearchResult,
)

__version__ = "0.1.0"

__all__ = [
    "ExplorationFilters",
    "ExplorationLimits",
    "ExplorationMode",
    "ExplorationResult",
    "ResearchBridge",
    "ResolvedPaper",
    "SearchLimits",
    "SearchResult",
    "__version__",
]
