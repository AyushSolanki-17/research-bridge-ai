"""Command-line entrypoint, independent of server dependencies."""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from datetime import date

from research_bridge import __version__
from research_bridge.ingestion.openalex.infrastructure.openalex_adapter import OpenAlexPaperAdapter
from research_bridge.knowledge_graph.application import (
    ExplorationCancelled,
    ExplorationLimits,
    ExploreOutgoing,
)
from research_bridge.research.papers.application import PaperProviderPort, ResolvePaper
from research_bridge.research.papers.application.errors import (
    PaperNotFoundError,
    ProviderMalformedResponseError,
    ProviderRateLimitedError,
    ProviderRetryExhaustedError,
    ProviderTimeoutError,
)
from research_bridge.research.papers.domain.identifiers import InvalidIdentifierError


def _json_default(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat().replace("+00:00", "Z")
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def run(argv: Sequence[str] | None = None, *, provider: PaperProviderPort | None = None) -> int:
    """Run research commands with optional injected acquisition.

    Args:
        argv: Command arguments, defaulting to process arguments.
        provider: Optional offline provider; otherwise compose OpenAlex.

    Returns:
        Exit code: 0 success, 2 invalid input, 3 missing seed, 4 upstream failure,
        5 truncated exploration, or 130 cancellation. Results are JSON on stdout;
        resolution errors are JSON on stderr. Parser help/errors use argparse.
    """
    parser = argparse.ArgumentParser(description="Research Bridge command-line tools")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command")
    resolve = commands.add_parser("resolve", help="Resolve a DOI or OpenAlex work identifier")
    resolve.add_argument("identifier")
    explore = commands.add_parser("explore", help="Explore outgoing citations within limits")
    explore.add_argument("identifier")
    defaults = ExplorationLimits()
    for name in ("depth", "max_nodes", "max_edges", "max_requests"):
        explore.add_argument(
            f"--{name.replace('_', '-')}", type=int, default=getattr(defaults, name)
        )
    explore.add_argument("--max-seconds", type=float, default=defaults.max_seconds)
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        acquisition = provider if provider is not None else OpenAlexPaperAdapter()
        if args.command == "resolve":
            record = asyncio.run(ResolvePaper(acquisition).execute(args.identifier))
            print(json.dumps(asdict(record), default=_json_default, allow_nan=False))
            return 0
        limits = ExplorationLimits(
            args.depth, args.max_nodes, args.max_edges, args.max_requests, args.max_seconds
        )
        graph = asyncio.run(ExploreOutgoing(acquisition).execute(args.identifier, limits))
        print(json.dumps(asdict(graph), default=_json_default, allow_nan=False))
        if graph.status == "truncated":
            return 5
        if graph.status == "failed":
            return 3 if "seed_not_found" in graph.stop_reasons else 4
        return 0
    except ExplorationCancelled as exc:
        print(json.dumps(asdict(exc.result), default=_json_default, allow_nan=False))
        return 130
    except (asyncio.CancelledError, KeyboardInterrupt):
        return 130
    except (
        InvalidIdentifierError,
        PaperNotFoundError,
        ProviderRateLimitedError,
        ProviderTimeoutError,
        ProviderMalformedResponseError,
        ProviderRetryExhaustedError,
        ValueError,
    ) as exc:
        if isinstance(exc, InvalidIdentifierError):
            code, message, status = "invalid_identifier", "Unsupported or malformed identifier.", 2
        elif isinstance(exc, PaperNotFoundError):
            code, message, status = "not_found", "Paper not found.", 3
        elif isinstance(exc, ProviderRateLimitedError):
            code, message, status = "rate_limited", "Provider rate limit reached.", 4
        elif isinstance(exc, ProviderTimeoutError):
            code, message, status = "provider_timeout", "Provider request timed out.", 4
        elif isinstance(exc, ProviderMalformedResponseError):
            code, message, status = "malformed_response", "Provider response is invalid.", 4
        elif isinstance(exc, ProviderRetryExhaustedError):
            code, message, status = "retries_exhausted", "Provider retries exhausted.", 4
        else:
            code, message, status = (
                "invalid_configuration",
                "Invalid limits or provider settings.",
                2,
            )
        print(json.dumps({"error": {"code": code, "message": message}}), file=sys.stderr)
        return status


def main() -> None:
    """Exit with the outcome of the requested command."""
    raise SystemExit(run())
