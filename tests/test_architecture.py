"""Check inward imports as capability implementations are introduced."""

import ast
import importlib.util
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src"
NAMESPACE = "research_bridge"


def test_inward_layer_dependencies() -> None:
    """Reject outward business imports and web dependencies outside the API package."""
    violations = []
    for path in (SOURCE / NAMESPACE).rglob("*.py"):
        parts = path.relative_to(SOURCE).with_suffix("").parts
        module = ".".join(parts)
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        source_layers = set(parts) & {"domain", "application", "interfaces", "infrastructure"}
        is_api = parts[:2] == (NAMESPACE, "api")
        for node in ast.walk(ast.parse(path.read_text())):
            targets = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                target = "." * node.level + (node.module or "")
                if node.level:
                    target = importlib.util.resolve_name(target, package)
                targets = [target, *(f"{target}.{alias.name}" for alias in node.names)]
            for target in targets:
                imported = set(target.split("."))
                forbidden = set()
                if not is_api:
                    forbidden |= {"fastapi", "starlette", "uvicorn"}
                if "domain" in source_layers:
                    forbidden |= {
                        "application",
                        "infrastructure",
                        "interfaces",
                        "fastapi",
                        "pydantic",
                        "sqlalchemy",
                        "uvicorn",
                    }
                if "application" in source_layers:
                    forbidden |= {"infrastructure", "interfaces", "fastapi", "uvicorn"}
                if "interfaces" in source_layers:
                    forbidden |= {"infrastructure"}
                entrypoint_import = any(
                    target == entrypoint or target.startswith(f"{entrypoint}.")
                    for entrypoint in (f"{NAMESPACE}.api", f"{NAMESPACE}.cli")
                )
                api_import = target == f"{NAMESPACE}.api" or target.startswith(f"{NAMESPACE}.api.")
                if (
                    forbidden & imported
                    or (source_layers and entrypoint_import)
                    or (not is_api and api_import)
                ):
                    violations.append(f"{path.relative_to(SOURCE)}:{node.lineno} imports {target}")
    assert not violations, "\n".join(violations)
