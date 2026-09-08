# Coding style and design

Use the existing manifest, lockfile, formatter and lint/type configuration as the executable style guide. Read neighboring code before introducing a convention. Follow Conventional Commits in CONTRIBUTING.md.

Keep each business invariant with one owner. Use domain/application/infrastructure/interfaces boundaries only where responsibilities require them. Prefer a small working vertical slice over empty layers or a framework of abstractions.

Apply SOLID pragmatically: cohesive responsibilities, narrow contracts, interchangeable implementations with the same semantics, and dependencies pointing toward business rules. Prefer composition over inheritance. Avoid global mutable state, service locators, god objects and generic utility buckets. Introduce a pattern only to solve a concrete problem and explain why.

Use Python 3.13, snake_case functions/modules, PascalCase classes, explicit type hints and strict mypy for source. Ruff owns formatting/import ordering and the 100-character line limit. Use immutable dataclasses/value objects for validated domain values when useful. Encapsulate invariants and state transitions in cohesive objects; simple stateless transformations can stay functions.

Use constructor injection for use cases and adapters. Define narrow typing.Protocol ports at external boundaries; use Repository for real persistence needs, Adapter for providers/transports, and Strategy only for actual interchangeable behavior. Avoid abstract base classes with one trivial implementation, deep inheritance and pass-through service classes. API and CLI entrypoints wire concrete dependencies.

For example, process health uses an application factory in `api/app.py` to compose the router in `api/health.py` and an immutable `HealthResponse` dataclass to define its response contract. Its stateless HTTP handler needs no service object. When a capability owns validated state or transitions, encapsulate those rules in domain objects; when a use case calls an external provider, inject an adapter through a narrow application-owned port. Each choice should follow the implemented responsibility.

Domain/application types must not depend on FastAPI, ORM or provider SDK objects. HTTP validation and HTTP schemas belong in `api/`; all FastAPI-specific behavior stays in that package. Business modules cannot import the API package or web framework. Other transport validation belongs in its own interfaces; domain validation protects invariants for all callers. Use specific errors and map them at boundaries. Bound network requests with timeouts/retries and propagate cancellation. Do not log credentials or full sensitive payloads.

Test observable behavior: domain invariants, use cases with fakes, adapter contracts with deterministic fixtures and important API/CLI journeys. Keep normal tests offline. Run README checks appropriate to changes; do not add tests solely to assert scaffold structure.

Follow the implementation discipline in AGENTS.md: task-linked changes, small verified slices, evidence-led debugging and a clear stopping condition. Design patterns are tools, not acceptance criteria.

## Docstrings and comments

Follow the mandatory [naming and documentation requirements](../AGENTS.md#naming-and-documentation-requirements). Apply the following documentation rules to new and changed handwritten code, including scripts and tests. Keep comments accurate when behavior changes; do not add empty sections or boilerplate that merely repeats names. Existing formatter, type-checker and line-length settings remain authoritative for code formatting.

For Python, follow the [Google Python comments and docstrings guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings). Use triple double quotes, a concise summary, and a blank line before further detail. Document modules, public classes and public functions/methods; explain non-obvious internal behavior. Include `Args:`, `Returns:` or `Yields:`, `Raises:` and class `Attributes:` sections when applicable. Describe observable behavior, meaningful constraints, side effects and expected errors without duplicating type annotations. Small, self-explanatory private helpers do not need redundant docstrings.

For any TypeScript/JavaScript added here, use [Google-style JSDoc](https://google.github.io/styleguide/tsguide.html#comments-documentation), with no duplicate TypeScript type annotations.

Comments must follow Google's clarity and grammar conventions: explain why, invariants or a surprising tradeoff; use clear sentences and avoid restating the code. Keep implementation details out of API documentation unless they affect callers. TODOs must describe concrete work and a traceable issue or owner, without roadmap labels. Review docstrings and comments for correctness, language-appropriate format and naming compliance before marking work complete.
