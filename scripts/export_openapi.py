"""Export the implemented API contract; --check fails on schema drift."""

import argparse
import json
from pathlib import Path

from research_bridge.api.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = Path(__file__).resolve().parents[1] / "contracts" / "openapi.json"
    schema = json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if not target.exists() or target.read_text() != schema:
            raise SystemExit(
                "OpenAPI drift: run uv run --extra server python scripts/export_openapi.py"
            )
    else:
        target.write_text(schema)


if __name__ == "__main__":
    main()
