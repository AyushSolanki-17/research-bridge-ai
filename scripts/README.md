# Repository scripts

Use standard tools directly for linting, formatting, types, tests and builds.
The root [Makefile](../Makefile) provides discoverable shortcuts; `make help` lists
them. CI shares its check/install targets. These scripts cover repository-specific
verification that the standard tools do not provide:

| Script | Purpose | Command |
| --- | --- | --- |
| `export_openapi.py` | Export the implemented HTTP contract; `--check` detects drift | `make schema` checks without rewriting |
| `verify_distribution.py` | Inspect wheel/source parity, boundaries, typing marker, metadata and documentation file links | `make dist` builds and inspects |
| `verify_installation.py` | Install both artifacts into temporary core-only environments, run isolated journeys and check installed consumer types | `make install-check` builds, inspects and installs |

The installation script reads the version from `pyproject.toml`, so release version
changes do not require edits to archive filenames in CI or local commands. Pass
`--python 3.13` or `--python 3.14`; `--dist-dir PATH` selects already built artifacts.
It needs uv and the project's development environment (including mypy), and removes
temporary environments on exit. The runtime journeys use loopback; dependency
installation can require the network.

For intentional contract changes, use the [contract commands](../contracts/README.md).
See [development](../docs/development.md) for direct commands and verification scope.
