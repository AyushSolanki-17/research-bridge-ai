"""Command-line entrypoint, independent of server dependencies."""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from datetime import date

from research_bridge import ResearchBridge, __version__
from research_bridge.core import (
    ExplorationCancelled,
    ExplorationFilters,
    ExplorationLimits,
    InvalidFilterError,
    InvalidIdentifierError,
    InvalidLimitsError,
    InvalidSearchError,
    PaperNotFoundError,
    ProviderMalformedResponseError,
    ProviderRateLimitedError,
    ProviderRetryExhaustedError,
    ProviderTimeoutError,
    SearchLimits,
    UnsupportedOperationError,
)
from research_bridge.providers.openalex import OpenAlexProvider


def _json_default(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat().replace("+00:00", "Z")
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def run(
    argv: Sequence[str] | None = None,
    *,
    bridge: ResearchBridge | None = None,
) -> int:
    """Run research commands through the same façade used by Python and HTTP.

    Args:
        argv: Command arguments, defaulting to process arguments.
        bridge: Optional configured business façade; defaults to OpenAlex.

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
    explore = commands.add_parser("explore", help="Explore citations within shared limits")
    explore.add_argument("identifier")
    explore.add_argument("--mode", choices=("outgoing", "incoming", "both"), default="outgoing")
    defaults = ExplorationLimits()
    for name in ("depth", "max_nodes", "max_edges", "max_requests"):
        explore.add_argument(
            f"--{name.replace('_', '-')}", type=int, default=getattr(defaults, name)
        )
    explore.add_argument("--max-seconds", type=float, default=defaults.max_seconds)
    for name in ("year_from", "year_to", "min_citations", "max_citations"):
        explore.add_argument(f"--{name.replace('_', '-')}", type=int)
    for name in ("author", "venue", "topic"):
        explore.add_argument(f"--{name}", help="Exact display name, ignoring case and whitespace")
    search = commands.add_parser(
        "search", help="Review title candidates before choosing an identifier"
    )
    search.add_argument("query")
    search.add_argument("--page", type=int, default=1)
    search_defaults = SearchLimits()
    for name in ("page_size", "max_results", "max_requests"):
        search.add_argument(
            f"--{name.replace('_', '-')}", type=int, default=getattr(search_defaults, name)
        )
    search.add_argument("--max-seconds", type=float, default=search_defaults.max_seconds)
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if bridge is None:
        try:
            bridge = ResearchBridge(OpenAlexProvider())
        except ValueError:
            print(
                json.dumps(
                    {
                        "error": {
                            "code": "invalid_configuration",
                            "message": "OpenAlex provider configuration is invalid.",
                        }
                    }
                ),
                file=sys.stderr,
            )
            return 2
    try:
        if args.command == "search":
            search_limits = SearchLimits(
                args.page_size, args.max_results, args.max_requests, args.max_seconds
            )
            result = asyncio.run(bridge.search(args.query, search_limits, page=args.page))
            print(json.dumps(asdict(result), default=_json_default, allow_nan=False))
            return 4 if result.status == "failed" else 5 if result.status == "truncated" else 0
        if args.command == "resolve":
            record = asyncio.run(bridge.resolve(args.identifier))
            print(json.dumps(asdict(record), default=_json_default, allow_nan=False))
            return 0
        limits = ExplorationLimits(
            args.depth, args.max_nodes, args.max_edges, args.max_requests, args.max_seconds
        )
        filter_values = {
            name: getattr(args, name)
            for name in (
                "year_from",
                "year_to",
                "min_citations",
                "max_citations",
                "author",
                "venue",
                "topic",
            )
            if getattr(args, name) is not None
        }
        filters = ExplorationFilters(**filter_values) if filter_values else None
        graph = asyncio.run(
            bridge.explore(args.identifier, limits, mode=args.mode, filters=filters)
        )
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
        InvalidLimitsError,
        InvalidFilterError,
        InvalidSearchError,
        UnsupportedOperationError,
        PaperNotFoundError,
        ProviderRateLimitedError,
        ProviderTimeoutError,
        ProviderMalformedResponseError,
        ProviderRetryExhaustedError,
    ) as exc:
        if isinstance(exc, InvalidIdentifierError):
            code, message, status = "invalid_identifier", "Unsupported or malformed identifier.", 2
        elif isinstance(exc, InvalidFilterError):
            code, message, status = "invalid_filters", "Invalid metadata filter values.", 2
        elif isinstance(exc, InvalidSearchError):
            code, message, status = "invalid_search", "Invalid title query or candidate page.", 2
        elif isinstance(exc, InvalidLimitsError):
            code, message, status = "invalid_limits", "Limits are outside the supported range.", 2
        elif isinstance(exc, UnsupportedOperationError):
            code, message, status = "unsupported_operation", "Operation is not configured.", 4
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
            raise AssertionError(f"unmapped CLI error: {type(exc).__name__}") from exc
        print(json.dumps({"error": {"code": code, "message": message}}), file=sys.stderr)
        return status


def main() -> None:
    """Exit with the outcome of the requested command."""
    raise SystemExit(run())
