# Coding style and design

Use the existing manifest, lockfile, formatter and lint/type configuration as the executable style guide. Read neighboring code before introducing a convention. Follow Conventional Commits in CONTRIBUTING.md.

Keep each business invariant with one owner. Use domain/application/infrastructure/interfaces boundaries only where responsibilities require them. Prefer a small working vertical slice over empty layers or a framework of abstractions.

Apply SOLID pragmatically: cohesive responsibilities, narrow contracts, interchangeable implementations with the same semantics, and dependencies pointing toward business rules. Prefer composition over inheritance. Avoid global mutable state, service locators, god objects and generic utility buckets. Introduce a pattern only to solve a concrete problem and explain why.

Use Python 3.13, snake_case functions/modules, PascalCase classes, explicit type hints and strict mypy for source. Ruff owns formatting/import ordering and the 100-character line limit. Use immutable dataclasses/value objects for validated domain values when useful. Encapsulate invariants and state transitions in cohesive objects; simple stateless transformations can stay functions.

Use constructor injection for use cases and adapters. Define narrow typing.Protocol ports at external boundaries; use Repository for real persistence needs, Adapter for providers/transports, and Strategy only for actual interchangeable behavior. Avoid abstract base classes with one trivial implementation, deep inheritance and pass-through service classes. API and CLI entrypoints wire concrete dependencies.

For example, process health uses an application factory in `api/app.py` to compose a capability-owned router and an immutable `HealthResponse` dataclass to define its response contract. Its stateless HTTP handler needs no service object. When a capability owns validated state or transitions, encapsulate those rules in domain objects; when a use case calls an external provider, inject an adapter through a narrow application-owned port. Each choice should follow the implemented responsibility.

Domain/application types must not depend on FastAPI, ORM or provider SDK objects. Transport validation belongs in interfaces; domain validation protects invariants for all callers. Use specific errors and map them at boundaries. Bound network requests with timeouts/retries and propagate cancellation. Do not log credentials or full sensitive payloads.

Test observable behavior: domain invariants, use cases with fakes, adapter contracts with deterministic fixtures and important API/CLI journeys. Keep normal tests offline. Run README checks appropriate to changes; do not add tests solely to assert scaffold structure.

Follow the implementation discipline in AGENTS.md: task-linked changes, small verified slices, evidence-led debugging and a clear stopping condition. Design patterns are tools, not acceptance criteria.
