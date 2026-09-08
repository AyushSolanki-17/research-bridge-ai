---
name: architecture-review
description: Review module dependencies, domain boundaries, research semantics and architectural complexity.
---

# Architecture Review

Evaluate architecture rather than formatting.

## Review dimensions

### Dependency direction

Confirm:

```
capability.interfaces → capability.application → capability.domain
capability.infrastructure → capability.application ports + capability.domain
api routers → capability.application
API assembly and CLI entrypoints → capability.infrastructure + capability.application
```

and infrastructure implements inward-facing contracts.

Flag inverted dependencies. All FastAPI code, HTTP schemas, routers, middleware and server setup belong under `src/research_bridge/api/`. Package code outside that directory must not import the API package, FastAPI, Starlette or Uvicorn.

### Reusability

Determine whether reusable business behavior can run independently of:

- FastAPI
- a specific database
- a specific cloud
- a specific scholarly-data provider
- a specific LLM provider

### Vendor coupling

Search for provider-specific concepts leaking beyond adapters.

Examples:

- provider SDK types in use cases
- AWS/GCP/Azure identifiers in domain entities
- OpenAlex-shaped models used as canonical models
- database-specific query semantics embedded in domain services
- model-provider request objects passed through application code

### Module and distribution quality

Check:

- cohesive responsibility
- minimal public API
- no circular dependency
- no oversized catch-all module
- optional heavy dependencies isolated
- consumer does not need unrelated infrastructure dependencies

### Data semantics

For Research Bridge specifically check:

- provenance retention
- confidence representation
- inference status
- relationship semantics
- citation versus influence distinction
- evidence traceability

### Operational architecture

Check:

- timeout behavior
- retry semantics
- idempotency
- bounded work
- transaction boundaries
- migration safety
- telemetry
- failure handling

### Complexity

Explicitly identify components that appear premature.

Ask:

> What demonstrated requirement requires this component?

Flag unjustified:

- microservices
- queues
- caches
- new databases
- workflow engines
- custom frameworks
- complex generic abstractions

## Output

Classify findings:

- BLOCKER
- HIGH
- MEDIUM
- LOW

For each meaningful finding provide:

1. problem
2. consequence
3. affected boundary
4. recommended correction

Also explicitly call out sound architectural decisions so they remain intentional.


## Ownership and reuse

Follow `CONTRIBUTING.md` for commit conventions and DRY review. Reuse the owning capability or released library before adding equivalent behavior. Keep generated contracts reproducible and maintain repository guidance locally.
