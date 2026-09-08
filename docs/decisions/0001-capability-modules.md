# ADR 0001: Source-root capability modules

Status: accepted. Supersedes the initial package-per-capability scaffold decision.

## Context

Business ownership, repository layout and independently reusable distributions are separate concerns. A logical capability does not require its own manifest or release lifecycle.

## Decision

Keep the application's source under `src/`. Group by business capability and use `domain/`, `application/`, `infrastructure/`, and `interfaces/` inside substantial capabilities. Keep internals flexible and add files only when behavior needs them. The `api/` package owns all FastAPI routes, HTTP schemas, dependencies and server setup. Business capabilities expose framework-independent application contracts that API routes call. Optional capability interfaces are for non-HTTP entrypoints only.

Reserve `packages/` for demonstrated standalone library extraction. Follow [architecture](../architecture.md) for repository-specific source paths and dependency rules.

## Consequences

Developers can locate a capability and its layers together. One root build/version covers the application source. Cross-capability imports require deliberate APIs and acyclic ownership; runtime dependencies stay out of domain/application imports. Add import checks with executable code. Revisit standalone libraries only for real independent consumers, not directory size or a conceptual boundary alone.
