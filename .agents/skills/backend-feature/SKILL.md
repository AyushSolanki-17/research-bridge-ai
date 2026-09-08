---
name: backend-feature
description: Implement a backend capability across its domain, use cases, adapters and entrypoints.
---

# Backend Feature

Implement backend features as vertical slices while preserving capability boundaries.

## Workflow

### 1. Understand

Read:

- `AGENTS.md`
- `docs/product.md` and `docs/architecture.md`
- affected capability documentation
- existing neighboring implementations

Determine the actual user-visible or application-visible capability being requested.

### 2. Find the owner

Determine where the behavior belongs.

Prefer:

- domain invariant → the owning capability’s `domain/`
- reusable use case → the owning capability’s `application/`
- external integration → the owning capability’s `infrastructure/`
- HTTP behavior → the capability’s `interfaces/api/`
- background execution → the capability’s `interfaces/worker/`

Never default business behavior to the API application merely because the feature begins with an HTTP endpoint.

### 3. Inspect existing contracts

Reuse appropriate existing:

- entities
- value objects
- ports
- repositories
- use cases
- error types

Do not create duplicate abstractions.

### 4. Design the vertical slice

Identify:

- domain behavior
- application orchestration
- required ports
- adapter changes
- API changes
- schema/migration changes
- observability
- tests

State meaningful concerns before implementation.

### 5. Implement inward-out

Preferred implementation order:

```
capability/domain
    ↓
application use case
    ↓
required ports
    ↓
infrastructure adapters
    ↓
capability interfaces, then assembly in API and CLI entrypoints
```

Keep the domain independent of infrastructure.

### 6. Test

Add the smallest sufficient combination of:

- domain unit tests
- use-case tests using fakes
- adapter contract/integration tests
- API tests
- E2E tests for important journeys

### 7. Review

Verify:

- no FastAPI dependency leaked into domain or application modules
- no ORM/provider object leaked inward
- public APIs changed intentionally
- errors are mapped correctly
- network calls have timeouts
- operations are bounded
- telemetry is adequate
- provenance/evidence semantics remain correct

### 8. Report

Summarize:

- implementation
- architectural decisions
- tests
- migrations
- compatibility impact
- meaningful follow-up work

Do not propose unrelated refactors unless they are required for correctness.

## Source placement

Use the owning capability under `src/`; put HTTP/CLI/job schemas and handlers in its interfaces layer. Keep concrete dependency wiring in API and CLI entrypoints. Mirror capability ownership in root `tests/`; coordinate schema changes in root `migrations/`. A feature does not need its own manifest or distribution.


## Ownership and reuse

Follow `CONTRIBUTING.md` for commit conventions and DRY review. Reuse the owning capability or released library before adding equivalent behavior. Keep generated contracts reproducible and maintain repository guidance locally.
