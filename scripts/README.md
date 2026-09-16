# Scripts

`export_openapi.py` exports the FastAPI schema to `contracts/openapi.json`; `--check` detects drift in CI. See the [contract commands](../contracts/README.md).

Use standard tools directly for linting, formatting, types, tests and builds. Add a script only for a concrete repeated task that those tools do not cover.

`verify_distribution.py` runs after `uv build` to guard source/wheel parity,
archive boundaries, documented inputs, local Markdown file links and installed
command/dependency metadata. It reads archives without extracting or installing
them. Pass `--dist-dir PATH` to inspect artifacts outside the default `dist/`.
