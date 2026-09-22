# Coding style and design

Use the existing manifest, lockfile, formatter and lint/type configuration as the executable style guide. Read neighboring code before introducing a convention. Follow Conventional Commits in CONTRIBUTING.md.

Keep each business invariant with one owner. Use the documented core/provider/transport
boundary and focused modules rather than ceremonial layer directories. Prefer a small
working vertical slice over empty layers or a framework of abstractions.

Apply SOLID pragmatically: cohesive responsibilities, narrow contracts, interchangeable implementations with the same semantics, and dependencies pointing toward business rules. Prefer composition over inheritance. Avoid global mutable state, service locators, god objects and generic utility buckets. Introduce a pattern only to solve a concrete problem and explain why.

Use Python 3.13, snake_case functions/modules, PascalCase classes, explicit type hints and strict mypy for source. Ruff owns formatting/import ordering and the 100-character line limit. Use immutable dataclasses/value objects for validated domain values when useful. Encapsulate invariants and state transitions in cohesive objects; simple stateless transformations can stay functions.

Use constructor injection for provider boundaries. Define narrow `typing.Protocol`
ports at external boundaries; use Repository for real persistence needs, Adapter for
providers/transports, and Strategy only for actual interchangeable behavior. Avoid
abstract base classes with one trivial implementation, deep inheritance and pass-through
service classes. `ResearchBridge` is the supported façade shared by Python, API and CLI.

For example, `api/router.py` closes over an injected `ResearchBridge` and contains only
HTTP translation. The standalone `api/app.py` chooses OpenAlex, while another FastAPI
application can mount the same router with its own façade. Operation state such as a
citation traversal is encapsulated per call; stateless mapping remains functions.

Core types and `ResearchBridge` must not depend on FastAPI, Pydantic, HTTPX, ORM or
provider SDK objects. HTTP validation and schemas belong in `api/`; provider networking
belongs in `providers/`. Core validation protects invariants for all callers. Use
specific errors and map them at boundaries. Bound network requests with timeouts and
finite retries, propagate cancellation, and never log credentials or full payloads.

Test observable behavior: domain invariants, use cases with fakes, adapter contracts with deterministic fixtures and important API/CLI journeys. Keep normal tests offline. Run README checks appropriate to changes; do not add tests solely to assert scaffold structure.

Follow the implementation discipline in AGENTS.md: task-linked changes, small verified slices, evidence-led debugging and a clear stopping condition. Design patterns are tools, not acceptance criteria.

## Docstrings and comments

Follow the mandatory [naming and documentation requirements](../AGENTS.md#naming-and-documentation-requirements). Apply the following documentation rules to new and changed handwritten code, including scripts and tests. Keep comments accurate when behavior changes; do not add empty sections or boilerplate that merely repeats names. Existing formatter, type-checker and line-length settings remain authoritative for code formatting.

For Python, follow the [Google Python comments and docstrings guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings). Use triple double quotes, a concise summary, and a blank line before further detail. Document modules, public classes and public functions/methods; explain non-obvious internal behavior. Include `Args:`, `Returns:` or `Yields:`, `Raises:` and class `Attributes:` sections when applicable. Describe observable behavior, meaningful constraints, side effects and expected errors without duplicating type annotations. Small, self-explanatory private helpers do not need redundant docstrings.

For any TypeScript/JavaScript added here, use [Google-style JSDoc](https://google.github.io/styleguide/tsguide.html#comments-documentation), with no duplicate TypeScript type annotations.

Comments must follow Google's clarity and grammar conventions: explain why, invariants or a surprising tradeoff; use clear sentences and avoid restating the code. Keep implementation details out of API documentation unless they affect callers. TODOs must describe concrete work and a traceable issue or owner, without roadmap labels. Review docstrings and comments for correctness, language-appropriate format and naming compliance before marking work complete.
