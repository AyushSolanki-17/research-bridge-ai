"""Enforce the small core/provider/transport dependency boundary."""

import ast
import importlib.util
from collections.abc import Iterator
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "src"
NAMESPACE = "research_bridge"
BOUNDARY_DEPENDENCIES = {"fastapi", "httpx", "httpx2", "pydantic", "starlette", "uvicorn"}


def _imports(source: str, package: str) -> Iterator[tuple[int, str]]:
    """Resolve static absolute, relative, and from-member imports."""
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


def _violation(module: str, target: str) -> str | None:
    """Return the reason an import crosses the documented package boundary."""
    external = target.split(".")[0]
    is_core = _within(module, f"{NAMESPACE}.core")
    is_bridge = module == f"{NAMESPACE}.bridge"
    is_provider = _within(module, f"{NAMESPACE}.providers")
    is_api = _within(module, f"{NAMESPACE}.api")
    is_cli = module == f"{NAMESPACE}.cli"

    if (is_core or is_bridge) and external in BOUNDARY_DEPENDENCIES:
        return "business code cannot depend on provider or transport libraries"
    if (is_core or is_bridge) and any(
        _within(target, f"{NAMESPACE}.{boundary}") for boundary in ("api", "providers", "cli")
    ):
        return "business code cannot depend on outer adapters"
    if is_provider and any(
        _within(target, f"{NAMESPACE}.{boundary}") for boundary in ("api", "cli")
    ):
        return "providers cannot depend on delivery interfaces"
    if is_api and module != f"{NAMESPACE}.api.app" and _within(target, f"{NAMESPACE}.providers"):
        return "only standalone app assembly may choose a concrete provider"
    if is_cli and external in {"fastapi", "pydantic", "starlette", "uvicorn"}:
        return "the CLI cannot depend on the optional server stack"
    if module == NAMESPACE and any(
        _within(target, f"{NAMESPACE}.{boundary}") for boundary in ("api", "providers", "cli")
    ):
        return "the public business package cannot eagerly import outer adapters"
    return None


def test_package_dependencies_point_outward_from_core() -> None:
    """Reject source imports that couple business logic to outer adapters."""
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
        ("core.explorer", "httpx"),
        ("core.search", "pydantic"),
        ("core.papers", "research_bridge.providers.openalex"),
        ("bridge", "research_bridge.api"),
        ("bridge", "research_bridge.providers.openalex"),
        ("providers.openalex.client", "research_bridge.api"),
        ("api.router", "research_bridge.providers.openalex"),
        ("cli", "fastapi"),
    ],
)
def test_rejects_forbidden_dependencies(module: str, target: str) -> None:
    """Prove representative boundary violations remain detectable."""
    assert _violation(f"{NAMESPACE}.{module}", target) is not None


@pytest.mark.parametrize(
    ("module", "target"),
    [
        ("bridge", "research_bridge.core"),
        ("providers.openalex.client", "research_bridge.core"),
        ("providers.openalex.client", "httpx"),
        ("api.router", "research_bridge.bridge"),
        ("api.router", "fastapi"),
        ("api.app", "research_bridge.providers.openalex"),
        ("cli", "research_bridge.providers.openalex"),
    ],
)
def test_allows_supported_dependencies(module: str, target: str) -> None:
    """Keep core use, concrete composition, and transport imports permitted."""
    assert _violation(f"{NAMESPACE}.{module}", target) is None


def test_resolves_relative_and_member_imports() -> None:
    """Prevent relative imports from bypassing dependency checks."""
    imports = set(
        _imports(
            "from ..providers import openalex\nfrom .ports import ResolvedPaper",
            "research_bridge.core",
        )
    )
    assert (1, "research_bridge.providers") in imports
    assert (2, "research_bridge.core.ports.ResolvedPaper") in imports
