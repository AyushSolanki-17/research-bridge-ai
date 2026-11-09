"""Framework-independent contracts and operations for Research Bridge."""

from research_bridge.core.budget import AcquisitionBudget, AcquisitionLimitReached
from research_bridge.core.citations import (
    CitationEdge,
    ExplorationCancelled,
    ExplorationLimits,
    ExplorationMode,
    ExplorationResult,
    IncomingPageGap,
    MetadataGap,
    UnresolvedReference,
)
from research_bridge.core.errors import (
    InvalidFilterError,
    InvalidIdentifierError,
    InvalidInputError,
    InvalidLimitsError,
    InvalidSearchError,
    PaperNotFoundError,
    ProviderMalformedResponseError,
    ProviderRateLimitedError,
    ProviderRetryExhaustedError,
    ProviderTimeoutError,
    ResearchBridgeError,
    UnsupportedOperationError,
)
from research_bridge.core.evidence import Evidence, InferenceStatus
from research_bridge.core.explorer import ExploreCitations
from research_bridge.core.filters import ExplorationFilters
from research_bridge.core.identifiers import Doi, OpenAlexWorkId, parse_identifier
from research_bridge.core.papers import Author, Paper, PaperIdentifiers, Topic, Venue
from research_bridge.core.ports import (
    CandidatePage,
    IncomingCitationPort,
    IncomingPage,
    PaperProviderPort,
    PaperSearchPort,
    ResolvedPaper,
)
from research_bridge.core.resolution import ResolvePaper
from research_bridge.core.search import SearchLimits, SearchPapers, SearchResult

__all__ = [
    "AcquisitionBudget",
    "AcquisitionLimitReached",
    "Author",
    "CandidatePage",
    "CitationEdge",
    "Doi",
    "Evidence",
    "ExplorationCancelled",
    "ExplorationFilters",
    "ExplorationLimits",
    "ExplorationMode",
    "ExplorationResult",
    "ExploreCitations",
    "IncomingCitationPort",
    "IncomingPage",
    "IncomingPageGap",
    "InferenceStatus",
    "InvalidFilterError",
    "InvalidIdentifierError",
    "InvalidInputError",
    "InvalidLimitsError",
    "InvalidSearchError",
    "MetadataGap",
    "OpenAlexWorkId",
    "Paper",
    "PaperIdentifiers",
    "PaperNotFoundError",
    "PaperProviderPort",
    "PaperSearchPort",
    "ProviderMalformedResponseError",
    "ProviderRateLimitedError",
    "ProviderRetryExhaustedError",
    "ProviderTimeoutError",
    "ResearchBridgeError",
    "ResolvedPaper",
    "ResolvePaper",
    "SearchLimits",
    "SearchPapers",
    "SearchResult",
    "Topic",
    "UnresolvedReference",
    "UnsupportedOperationError",
    "Venue",
    "parse_identifier",
]
