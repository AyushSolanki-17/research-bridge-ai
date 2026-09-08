---
name: persistence-change
description: Change persistence ports, queries, transactions, migrations and backfills.
---

# Persistence Change

Persistence is an adapter concern.

## Before implementation

Determine:

- application capability required
- existing port representing it
- transactional requirements
- expected data volume
- consistency requirements
- query access pattern

Do not begin by exposing a database primitive to application code.

## Port design

Ports should describe application capabilities.

Prefer:

```
relationship_repository.find_paths(...)
```

over:

```
database.run_query(...)
```

Keep database-specific optimizations behind implementations.

## Domain separation

Never expose outward:

- ORM session
- ORM entity
- database connection
- query-builder object

Translate persisted representations into canonical/domain representations.

## Queries

Consider:

- indexes
- cardinality
- bounds
- pagination
- execution plan where important
- N+1 behavior
- locking
- transaction isolation
- concurrent updates

Graph traversal requires explicit depth/node/result limits.

## Migrations

For production schema changes determine whether expand/migrate/contract is required.

Avoid destructive operations until compatible application versions no longer depend on old structures.

Backfills should be:

- resumable
- observable
- bounded
- safe to retry where practical

Provide rollback or forward-recovery reasoning for important changes.

## Database neutrality

Do not pretend all databases provide identical behavior.

When using database-specific features:

- isolate them in the adapter
- document the capability
- keep domain/application contracts vendor-neutral where meaningful
- provide an alternate adapter only when there is an actual requirement for one

Database agnosticism means replaceable architecture, not refusing to use useful database capabilities.

## Repository locations

Repository ports belong in the consuming capability’s application layer; concrete persistence belongs in its infrastructure layer. Root `migrations/` coordinates ordered schema changes with explicit capability ownership. Do not create a separate distribution for an adapter without independent consumers.


## Ownership and reuse

Follow `CONTRIBUTING.md` for commit conventions and DRY review. Reuse the owning capability or released library before adding equivalent behavior. Keep generated contracts reproducible and maintain repository guidance locally.
