# Outgoing citation exploration

`application.ExploreOutgoing(provider).execute(seed, limits)` accepts a DOI/work
identifier or an already ingested `ResolvedPaper`. It returns canonical papers,
directed citation edges and their evidence through framework-independent contracts.
The provider must implement the paper application port's optional `budget` argument.

## Traversal and limits

Traversal is breadth-first. The seed is at depth zero; depth 1 includes its
references, depth 2 includes their references, and depth 3 includes one further
hop. Nodes at the requested boundary are acquired but not expanded. Each reference
list is deduplicated and sorted lexically by normalized identifier. Nodes and
source/target edge pairs are deduplicated, including merged targets. Cycles stop
without reacquisition. A merged target retains the original `referenced_id` in
its edge evidence even when the endpoint uses the canonical identity.

| Limit | Default | Hard maximum |
| --- | --- | --- |
| Depth | 1 | 3 |
| Acquired papers | 50 | 500 |
| Directed edges | 200 | 2000 |
| Physical provider requests | 100 | 1000 |
| Elapsed seconds | 30 | 120 |

All count limits must be positive integers, and elapsed time must be finite and
positive. The seed counts as a node; acquiring a raw seed consumes requests.
An already ingested seed consumes no new request. Retries and every redirect
consume requests before they start. Singleton outgoing lookup has no pagination.
One operation budget spans seed acquisition, traversal, retries and backoff;
the adapter caps each network wait to the remaining elapsed allowance. The clock
is injectable for deterministic tests. Reaching a count limit is not itself
truncation: a result is complete if no additional work is needed. Reaching the
elapsed deadline stops work, including a response arriving exactly at that time.

## Evidence and completion

Edges mean citing paper → referenced paper, never inferred influence. Evidence
retains the citing record's provider, source URL and observation time. Stable
assertion identity is `provider:citation:record-id:referenced-id`; OpenAlex uses
the existing `openalex:citation:W…:W…` identity. The `referenced_id` names the exact
reference assertion before merge resolution.

- `complete`: acquisition exhausted within the requested depth. This never
  claims corpus-wide completeness or complete metadata.
- `truncated`: `nodes`, `edges`, `requests`, `elapsed_time`,
  `unresolved_references` or `incomplete_references` prevented complete acquisition.
- `failed`: `provider_failure` or `seed_not_found`; acquired data is retained.

`unresolved` names the target and reason when a reference cannot be acquired;
an edge may point to such a target without an acquired paper node. A limit may
stop before that edge is inserted. Stop reasons mean additional traversal remains,
not that the unresolved list enumerates every unvisited reference. Missing targets
are not fetched repeatedly. `incomplete_metadata` lists unavailable fields on
acquired papers. Missing/malformed reference lists truncate only when the work
must be expanded; a known empty list does not. Other metadata gaps do not imply
the requested citation neighborhood is incomplete.

Cancellation raises `ExplorationCancelled`, an `asyncio.CancelledError` subtype,
with the partial result in `.result`, status `failed` and reason `cancelled`.
No further acquisition is attempted. Invalid identifiers and limits raise before
provider work. Callers own injected clients; the adapter closes clients it creates.

Tests in `tests/knowledge_graph` cover hop depth, direction, evidence, cycles,
merges, exact limits, controlled elapsed time, missing data and partial failures.
`tests/ingestion/openalex/test_operation_budget.py` verifies physical HTTP
accounting for retries and redirects. HTTP and CLI call these same contracts;
see the [runtime examples](../../../README.md).

See [architecture](../../../docs/architecture.md).
