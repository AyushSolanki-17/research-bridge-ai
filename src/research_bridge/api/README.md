# API

All FastAPI implementation lives here: application assembly, routers, HTTP schemas,
dependencies, middleware and server startup. Add modules only when behavior needs them.
Business packages outside `api/` expose framework-independent application contracts;
routes call those contracts without moving business rules into HTTP handlers.

- `app.py` creates the FastAPI application and registers routers.
- `health.py` owns the health router and immutable `HealthResponse` HTTP schema.
- `server.py` reads host/port settings and launches Uvicorn.

`GET /health` returns HTTP 200 with `{"status": "ok"}`. It reports process liveness
without checking a database or external provider. `tests/api/test_health.py` verifies
the response; `contracts/openapi.json` records the exported contract.

## Research contracts

`POST /v1/papers/resolve` accepts `{"identifier":"10.7717/peerj.4375"}` and
returns a `ResolvedPaper`. `POST /v1/graphs/outgoing` accepts an identifier plus
an optional `limits` object (`depth`, `max_nodes`, `max_edges`, `max_requests`,
`max_seconds`) and returns an `ExplorationResult`. Unknown request fields and
invalid field types are rejected. Identifiers are limited to 2048 characters.
The application owns normalization, numeric bounds, traversal and evidence rules;
the router only translates input and maps outcomes to HTTP. `app.py` composes
the shared provider and use cases; tests inject an offline provider.

Both operations acquire data without modifying remote records, require no
application authentication and support arbitrary identifiers. Repeated requests
may reflect newer provider metadata and observation times; no caching is implied.
Outgoing singleton lookup has no pagination. Results use deterministic breadth-first
ordering and limits documented in [knowledge graph](../knowledge_graph/README.md).

| Outcome | HTTP response |
| --- | --- |
| Resolved paper | 200, paper and evidence |
| Complete or truncated graph | 200, graph with explicit status and stop reasons |
| Invalid identifier or limits | 422, error envelope |
| Invalid JSON, fields or types | 422, `invalid_request` error envelope |
| Missing paper | 404, `not_found` error envelope |
| Resolution rate limit | 429, `rate_limited` error envelope |
| Resolution timeout | 504, `provider_timeout` error envelope |
| Resolution malformed response / exhausted retries | 502, `malformed_response` / `retries_exhausted` |
| Graph seed missing | 404, failed graph with `seed_not_found` |
| Graph provider failure | 502, failed graph retaining acquired data |

Error envelopes contain `error.code` and a safe `error.message`; internal upstream
exception text is not returned. Validation codes are `invalid_identifier`,
`invalid_limits` or `invalid_request`. Graph cancellation propagates and stops
acquisition, rather than returning a successful response. The library exception
retains the partial result; delivery over a cancelled connection is not guaranteed.
Missing metadata remains null or empty collections. IDs use `{"value":"W…"}`
objects; source evidence includes an inspectable URL and observation timestamp.
Every unresolved edge target is identified in the graph's `unresolved` entries.

`tests/test_research_journeys.py` compares library, HTTP and CLI output against the
same deterministic provider, including truncation, partial failures and safe errors.
The independent command-line entrypoint lives in `research_bridge/cli.py`.
See the [runtime commands](../../../README.md).

## Title candidate search

`POST /v1/papers/search` accepts `query`, optional one-based `page` and optional
`limits` (`page_size`, `max_results`, `max_requests`, `max_seconds`). It returns
`SearchResult` with attributed canonical candidates, `next_page`, status, stop
reasons, applied bounds and physical request count. See the
[paper search contract](../research/papers/README.md#title-candidate-search).

Complete, more and truncated searches return HTTP 200. Provider failures return
HTTP 502 with the partial `SearchResult`, not a resolution error envelope. Invalid
query/page yields 422 `invalid_search`; invalid bounds yield 422 `invalid_limits`;
invalid transport shape/types yield 422 `invalid_request`. Cancellation propagates.
Search does not choose a seed: submit the reviewed identifier to an existing resolve
or outgoing graph endpoint. All search requests are read-only and unauthenticated.
Tests can inject a separate `search_provider` into `create_app` or CLI `run`.

## Citation direction modes

`POST /v1/graphs/explore` accepts `identifier`, optional `limits` and optional
`mode`: `outgoing` (default), `incoming` or `both`. All modes share the graph
response and HTTP status mapping above. Results also expose applied `mode` and
`unread_incoming_pages` (`target`, opaque provider `cursor`, `reason`) for an
interrupted incoming page. These fields are additive to outgoing results.
Invalid modes return 422 `invalid_request`; incomplete acquisition never becomes
a successful complete graph. Incoming/combined requests use the same operation
limits across seed, directions, cursor pages and retries. See the
[traversal contract](../knowledge_graph/README.md#incoming-and-combined-traversal).

`/v1/graphs/outgoing` retains its outgoing-only request shape. `create_app` and CLI
`run` accept an optional `incoming_provider`; otherwise the lookup provider is
used if it implements incoming acquisition. Custom lookup-only providers remain
usable for outgoing requests; incoming mode without a boundary fails before I/O.
