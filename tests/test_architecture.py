"""Check inward imports as capability implementations are introduced."""

import ast
import importlib.util
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src"
NAMESPACE = "research_bridge"


def test_inward_layer_dependencies() -> None:
    violations = []
    for path in (SOURCE / NAMESPACE).rglob("*.py"):
        parts = path.relative_to(SOURCE).with_suffix("").parts
        module = ".".join(parts)
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        source_layers = set(parts) & {"domain", "application", "interfaces", "infrastructure"}
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
                if "domain" in source_layers:
                    forbidden |= {
                        "application",
                        "infrastructure",
                        "interfaces",
                        "bootstrap",
                        "fastapi",
                        "pydantic",
                        "sqlalchemy",
                        "uvicorn",
                    }
                if "application" in source_layers:
                    forbidden |= {"infrastructure", "interfaces", "bootstrap", "fastapi", "uvicorn"}
                if "interfaces" in source_layers:
                    forbidden |= {"infrastructure", "bootstrap"}
                if source_layers and "bootstrap" in imported:
                    forbidden.add("bootstrap")
                if forbidden & imported:
                    violations.append(f"{path.relative_to(SOURCE)}:{node.lineno} imports {target}")
    assert not violations, "\n".join(violations)
