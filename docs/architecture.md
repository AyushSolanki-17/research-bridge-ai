# Architecture

Status: the library, HTTP and CLI resolve identifiers and explore bounded outgoing citation neighborhoods through the same application use cases. OpenAlex acquisition counts physical requests, redirects and retries against operation budgets. Knowledge graph owns breadth-first traversal, directed edges, evidence and partial-result semantics. API assembly and CLI compose the provider; HTTP schemas and error mapping stay in `api/`. Title candidate search is owned by the paper application through a separate search port; the OpenAlex adapter reuses bounded HTTP acquisition and canonical metadata translation. Stateless public pages replay and deduplicate provider cursor pages. See [runtime commands](../README.md).

## Source layout

```text
src/research_bridge/
  research/papers/
  knowledge_graph/
  provenance/
  ingestion/openalex/
  api/                         all FastAPI code: app, routes, HTTP schemas and server
  cli.py                       command-line entrypoint
tests/                         mirrors source capabilities and cross-capability journeys
migrations/                    ordered schema changes with capability ownership
scripts/                       OpenAPI contract export
contracts/                     this backend's API schema policy
docs/                          product, architecture and decisions
.agents/skills/                 focused implementation workflows
```

| Source module | Owns |
|---|---|
| `research/papers/` | Canonical scholarly works, identifiers and paper metadata. Add other research entities only when a query needs them. |
| `knowledge_graph/` | Typed relationships, graph persistence, bounded traversal and paths. |
| `provenance/` | Evidence records, source attribution and confidence semantics. Evidence references remain stable across ingestion, graph queries and answers. |
| `ingestion/openalex/` | OpenAlex acquisition and normalization into canonical research records. Provider payloads and SDKs stay in infrastructure; application code coordinates bounded, resumable ingestion through ports. |

## Capability convention

Business capabilities use these boundaries only where needed; HTTP transport lives separately in `api/`:

```text
<capability>/
  __init__.py                  intentional exports, no eager infrastructure imports
  domain/                      entities, value objects, invariants, domain errors
  application/                 use cases, commands/queries, DTOs and required ports
  infrastructure/              persistence, providers and implementations of ports
  interfaces/                  optional non-HTTP handlers, independent of FastAPI
```

A directory or file exists only when its responsibility is needed. Small capabilities can begin with `domain/entities.py` or one use case. Do not create boilerplate services, repositories, factories or validators just to match a template. A repository abstraction belongs beside its consuming use case in `application/`; an implementation belongs in `infrastructure/`. Place a port in domain only when a domain operation itself requires that abstraction.

Application `schemas.py` means framework-independent command/result DTOs. HTTP request/response schemas, routers, dependencies, middleware and server setup belong exclusively to `src/research_bridge/api/`. Domain errors express invariants; application errors express use-case failures; API handlers translate them into HTTP errors; other interfaces translate them for their own transport. `service.py` is optional and should represent a named use case or cohesive behavior, not an all-purpose manager.

## Dependency direction

```text
interfaces     → application → domain
infrastructure → application ports + domain
api routes     → application contracts
api app / cli  → infrastructure + application
```

Domain does not import application, infrastructure, interfaces, FastAPI, ORM or provider SDK types. Application does not import infrastructure or interfaces. Interfaces call use cases and receive dependencies; they do not construct concrete adapters. API assembly and CLI entrypoints construct concrete dependencies without business rules. API routers receive dependencies and call supported application contracts. All package code outside `api/` is independent of FastAPI, Starlette, Uvicorn and `research_bridge.api`.

Across capabilities, import supported application exports or stable domain value types; never another capability's infrastructure, interface internals or tables. An `__init__.py` exports only deliberately supported symbols when implementation exists. Prevent circular dependencies with consumer-owned ports and entrypoint-wired adapters. Adapters may call another capability's supported application contract without making the consumer's application layer import its implementation. Use direct calls before introducing messaging.

## Persistence, tests and runtime

Keep the root `pyproject.toml` and `uv.lock`; no workspace or per-capability distribution is needed. Root `migrations/` owns ordered database migrations, with explicit capability ownership on every change. Capabilities own writes to their data; cross-capability writes go through use cases. Document consistency, backfill resumability, rolling compatibility and recovery. Add Alembic configuration only when relational migrations exist.

Mirror source ownership in `tests/`; separate domain/use-case tests, adapter integrations and API/CLI journeys as needed. CI runs lint/type checks, static inward-import enforcement, API tests, deterministic schema export and package/container builds. Static import checks do not resolve runtime imports or prove all cross-capability API rules. Tests must prove behavior and boundaries, not that empty scaffold files exist.

Python, FastAPI, uv and pytest remain the implementation direction. Dependency manifests, lockfiles, Dockerfile and runnable instructions are now present. Database, graph, vector, LLM and queue adapters are selected for demonstrated workloads. Bound graph depth, nodes, edges, results and time; preserve cancellation, source evidence and explicit inference status. Apply external timeouts, bounded retries and operation-scoped idempotency.

## Reusable distributions

A business module is not a separately released library. The root Python project may publish a single distribution from `src/`, exposing a small documented application API. Keep transport/provider dependencies optional and avoid eager imports so programmatic use does not start servers or require unrelated infrastructure.

Reserve `packages/` for a proven independently installable library with its own consumer need, API, dependencies, build and compatibility lifecycle. Do not create that directory until an extraction is justified. A logical domain boundary alone is not a reason to extract a distribution.

## Cross-capability rules

Research may depend on stable provenance value types. Knowledge graph may depend on research and provenance. Ingestion coordinates writes through supported research and graph application contracts; those lower layers never import ingestion. Keep one canonical paper model and map it into graph representations. Source attribution belongs in provenance; acquisition belongs in ingestion.

## First implementation

Follow [next steps](next-steps.md) for the seed resolution and bounded citation explorer milestone and [coding style](coding-style.md) for OOP and design guidance.
