"""Enforce inward dependencies and the documented capability dependency graph."""

import ast
import importlib.util
from collections.abc import Iterator
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "src"
NAMESPACE = "research_bridge"
LAYERS = {"domain", "application", "interfaces", "infrastructure"}
CAPABILITIES = {
    "provenance": set(),
    "research.papers": {"provenance"},
    "knowledge_graph": {"research.papers", "provenance"},
    "ingestion.openalex": {"research.papers", "knowledge_graph", "provenance"},
}


def _imports(source: str, package: str) -> Iterator[tuple[int, str]]:
    """Resolve static imports, including relative and from-package member imports."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            target = "." * node.level + (node.module or "")
            if node.level:
                target = importlib.util.resolve_name(target, package)
            yield node.lineno, target
            for alias in node.names:
                yield node.lineno, f"{target}.{alias.name}"


def _within(module: str, parent: str) -> bool:
    return module == parent or module.startswith(f"{parent}.")


def _owner(module: str) -> str | None:
    return next((name for name in CAPABILITIES if _within(module, f"{NAMESPACE}.{name}")), None)


def _violation(module: str, target: str) -> str | None:
    """Explain an illegal dependency without matching unrelated external name segments."""
    source_layers = set(module.split(".")) & LAYERS
    target_layers = set(target.split(".")) & LAYERS
    is_internal = _within(target, NAMESPACE)
    is_api = _within(module, f"{NAMESPACE}.api")
    external = target.split(".")[0]
    if not is_api and external in {"fastapi", "starlette", "uvicorn"}:
        return "web dependencies belong in api"
    if not is_api and _within(target, f"{NAMESPACE}.api"):
        return "business code cannot depend on api"
    if source_layers and _within(target, f"{NAMESPACE}.cli"):
        return "business code cannot depend on cli"
    if source_layers & {"domain", "application"} and external in {
        "httpx",
        "httpx2",
        "pydantic",
        "sqlalchemy",
    }:
        return "provider, transport and persistence dependencies belong at the boundary"
    if is_internal:
        forbidden = set()
        if "domain" in source_layers:
            forbidden |= {"application", "infrastructure", "interfaces"}
        if "application" in source_layers:
            forbidden |= {"infrastructure", "interfaces"}
        if "interfaces" in source_layers:
            forbidden.add("infrastructure")
        if forbidden & target_layers:
            return "layers must depend inward"
        if is_api and module != f"{NAMESPACE}.api.app" and "infrastructure" in target_layers:
            return "only api.app composes concrete adapters"
        owner, dependency = _owner(module), _owner(target)
        if owner is not None and dependency is not None and owner != dependency:
            if dependency not in CAPABILITIES[owner]:
                return "dependency reverses capability ownership"
            if target_layers & {"infrastructure", "interfaces"}:
                return "cross-capability imports must use application contracts or domain values"
    return None


def test_inward_layer_dependencies() -> None:
    """Reject actual source dependencies that break layer or capability ownership."""
    violations = set()
    for path in (SOURCE / NAMESPACE).rglob("*.py"):
        parts = path.relative_to(SOURCE).with_suffix("").parts
        module = ".".join(parts[:-1] if path.name == "__init__.py" else parts)
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        for line, target in _imports(path.read_text(), package):
            reason = _violation(module, target)
            if reason:
                violations.add(f"{path.relative_to(SOURCE)}:{line} imports {target}: {reason}")
    assert not violations, "\n".join(sorted(violations))


@pytest.mark.parametrize(
    ("module", "target"),
    [
        ("research.papers.domain.paper", "research_bridge.research.papers.application"),
        ("research.papers.application.resolve_paper", "httpx"),
        ("research.papers.application.resolve_paper", "pydantic"),
        ("research.papers.domain.paper", "starlette.responses"),
        ("provenance.domain.evidence", "research_bridge.research.papers.domain.paper"),
        ("research.papers.application.ports", "research_bridge.knowledge_graph.application"),
        ("knowledge_graph.application.explore", "research_bridge.ingestion.openalex"),
        (
            "ingestion.openalex.infrastructure.translation",
            "research_bridge.provenance.infrastructure",
        ),
        ("research.papers.interfaces.worker", "research_bridge.research.papers.infrastructure"),
        ("api.research", "research_bridge.ingestion.openalex.infrastructure.openalex_adapter"),
        ("knowledge_graph.application.explore", "research_bridge.api.app"),
        ("research.papers.application.ports", "research_bridge.cli"),
        ("cli", "fastapi"),
    ],
)
def test_rejects_forbidden_dependencies(module: str, target: str) -> None:
    """Prove the guard catches representative violations, even when source is clean.

    Args:
        module: Consumer module relative to the package root.
        target: Absolute dependency that the architecture prohibits.
    """
    assert _violation(f"{NAMESPACE}.{module}", target) is not None


@pytest.mark.parametrize(
    ("module", "target"),
    [
        ("api.app", "research_bridge.ingestion.openalex.infrastructure.openalex_adapter"),
        ("cli", "research_bridge.ingestion.openalex.infrastructure.openalex_adapter"),
        ("api.research", "research_bridge.knowledge_graph.application"),
        ("knowledge_graph.application.explore", "research_bridge.research.papers.application"),
        ("research.papers.domain.paper", "research_bridge.provenance.domain.evidence"),
        ("ingestion.openalex.infrastructure.openalex_adapter", "httpx"),
        (
            "ingestion.openalex.infrastructure.openalex_adapter",
            "research_bridge.knowledge_graph.application",
        ),
        ("research.papers.domain.paper", "example.application"),
    ],
)
def test_allows_supported_dependencies(module: str, target: str) -> None:
    """Keep legitimate composition, value reuse and unrelated external imports allowed.

    Args:
        module: Consumer module relative to the package root.
        target: Absolute dependency permitted by the architecture.
    """
    assert _violation(f"{NAMESPACE}.{module}", target) is None


def test_resolves_relative_and_member_imports() -> None:
    """Prevent relative imports and from-package imports from bypassing the guard."""
    imports = set(
        _imports(
            "from .. import infrastructure\nfrom .ports import ResolvedPaper",
            "research_bridge.research.papers.application",
        )
    )
    assert (1, "research_bridge.research.papers.infrastructure") in imports
    assert (2, "research_bridge.research.papers.application.ports.ResolvedPaper") in imports
