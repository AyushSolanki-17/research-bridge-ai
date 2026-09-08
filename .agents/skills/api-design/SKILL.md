---
name: api-design
description: Design or change FastAPI endpoints and versioned API contracts.
---

# FastAPI API Design

Treat FastAPI as an outer transport adapter. Keep all FastAPI implementation under `src/research_bridge/api/`, including routers, HTTP schemas, dependency functions, middleware, app assembly and server startup. Business packages must not import this package or the web framework.

## Endpoint workflow

For each endpoint identify:

- actor
- operation
- request contract
- application use case
- response contract
- authorization requirement
- failure cases
- boundedness
- idempotency requirement

The normal flow is:

```
request schema
    ↓
transport translation
    ↓
capability use case
    ↓
result
    ↓
response schema
```

## Requirements

Routers must remain thin.

Do not place domain decisions in:

- routers
- Pydantic validators
- dependency functions
- middleware

unless the decision genuinely concerns HTTP transport.

Do not expose:

- ORM models
- provider SDK models
- internal exceptions
- database identifiers that are not public identifiers

Map application errors centrally and consistently.

For collections define:

- pagination
- limits
- ordering behavior
- filtering semantics

Reject or bound expensive graph/query operations.

Use explicit request size and parameter limits where relevant.

For mutable operations determine whether retry/idempotency protection is necessary.

Avoid breaking response contracts without explicit intent.

Keep HTTP-specific schemas and handlers in `src/research_bridge/api/`; group by capability inside this folder when needed. Call the business capability’s supported application contracts.

If a data structure must become a reusable programmatic contract, define an appropriate application-level DTO deliberately rather than importing API schemas into business modules.

## Tests

Test:

- validation
- happy path
- expected errors
- authorization
- status codes
- response schema
- pagination/limits
- idempotency where relevant


## Ownership and reuse

Follow `CONTRIBUTING.md` for commit conventions and DRY review. Reuse the owning capability or released library before adding equivalent behavior. Keep generated contracts reproducible and maintain repository guidance locally.
