# Bounded citation exploration

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

## Incoming and combined traversal

`ExploreCitations(provider, incoming_provider=None).execute(seed, limits, mode="incoming")`
supports `outgoing`, `incoming` and `both`. `ExploreOutgoing` is a compatibility
alias with the same outgoing default. Incoming modes require `IncomingCitationPort`:
use an explicit injected boundary, or a lookup provider implementing `fetch_incoming`.
Missing incoming support or an invalid mode raises `ValueError` before acquisition.

At each breadth-first node, `both` processes lexically ordered outgoing references,
then all incoming cursor pages in provider order. Incoming works are consumed in
page order, with canonical node and directed edge deduplication. First observation
wins for repeated nodes/edges. The same directions apply at every hop; depth counts
discovery hops even when an incoming edge points toward the shallower node.
Nodes at the depth boundary are not expanded. Cycles do not trigger re-expansion.
Ordering is deterministic for identical provider responses, not a frozen corpus view.

All directions and pages share the existing request/time/node/edge bounds. Earlier
outgoing work or incoming pages may use the remaining budget before later work.
Incoming acquisition requests up to 100 records per page; `max_nodes` bounds retained
graph nodes, with one provider page temporarily buffered. A full node/edge bound
can require a further page to prove exhaustion or discover additional work. Duplicate
and empty pages still consume requests; changing cursors cannot bypass the budget.
Repeated cursors truncate with `repeated_cursor`. Reaching a limit never implies
provider exhaustion, even if the page's declared citation count suggests it.

Incoming lookup uses the provider's citing-work operation, not local inversion of
the acquired graph. Every incoming edge uses the citing record's explicit
`referenced_works` assertion and the same stable evidence identity as outgoing
edges. If a returned work lacks that exact normalized target (including unresolved
merged identifiers), the result fails with `provider_failure` and retains earlier
data. The filter response alone does not substitute for missing record evidence.
Missing references on a node do not truncate incoming-only expansion; missing
outgoing metadata remains visible in `incomplete_metadata`.

Results include the applied `mode`. `unread_incoming_pages` identifies an interrupted
page by `target`, opaque `cursor` and `reason`, including acquisition failure,
deadline, cancellation or stopping partway through its records. This is diagnostic
context, not a public resume token. Retry the whole operation with appropriate
limits; provider changes can affect membership. It does not enumerate pages of
every queued, unexpanded node. `unresolved` retains outgoing-reference and seed
failures; `stop_reasons` describes the overall incomplete scope.
