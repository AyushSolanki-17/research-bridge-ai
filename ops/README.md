# Operations

The root Dockerfile installs the frozen server dependencies with uv and runs under an unprivileged user. It copies only the root build metadata and `src/`, with a restricted `.dockerignore`. The runtime listens on port 8000 inside the container; see [README](../README.md) for local mapping.

`GET /health` reports process availability. Add readiness probes when external dependencies exist. No database, migrations, queues or production environment configuration are provisioned by this bootstrap. GitHub CI validates and builds images without publishing or deploying them.
