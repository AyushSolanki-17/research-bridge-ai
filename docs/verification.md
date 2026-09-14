# Backend verification evidence

Verified 2026-09-13 against this checkout. The completed capability tasks were
rechecked, and server/container execution, live-provider compatibility and archive
content verification were added as concrete follow-ups. This records observed
results; it does not claim exhaustive correctness or permanent provider availability.

## Offline regression and installed runtime

| Check | Result |
| --- | --- |
| `uv run ruff check .` | Passed. |
| `uv run ruff format --check .` | Passed. |
| `uv run --extra server mypy` | Passed for 25 source files. |
| `uv run --extra server pytest` | 244 passed; two existing dependency warnings. |
| `uv run --extra server python scripts/export_openapi.py --check` | Passed; no HTTP contract changes. |
| `uv build` | Wheel and source distribution built. |
| `uv run python scripts/verify_distribution.py` | Source parity, archive paths, local documentation links, commands and optional dependencies passed. |
| `uv run --extra server python tests/runtime_smoke.py` | Real API process, HTTP requests, CLI processes and graceful shutdown passed. |
| Clean source-distribution installation | Built/installed in a fresh Python 3.13 environment; its extracted standalone journey passed with `-I --require-core-only`. FastAPI, Starlette, Uvicorn and pytest were absent. |

The prior clean-wheel check also passed and remains in CI. The normal suite covers
identifier normalization, metadata translation, title ambiguity/pagination, all
citation modes/depths, cycles/merges, filtering, evidence, exact bounds, retries,
cancellation and partial failures. The process smoke reuses those journey fixtures
through actual sockets and installed commands, including served docs/OpenAPI,
invalid JSON/limits/filters, missing papers and incoming-page failures.

The archive checker was also run against deliberately damaged copies: missing
`docs/architecture.md`, changed wheel code and mandatory server dependencies were
all rejected. No negative-test artifact replaced the real distribution.

The first smoke assertion incorrectly expected exit zero from a signaled child.
Inspection of installed Uvicorn showed that it re-raises SIGTERM after completing
lifespan shutdown. The check now requires that expected signal exit, a completed
shutdown log and no traceback or forced kill. This is distinct from the container's
PID 1, which completed `docker stop` with exit zero.

## Docker execution

Docker Desktop was started. The first build timed out while the Docker credential
helper stalled. Host registry access worked; a temporary anonymous Docker config
avoided that helper for the public base images, and the documented Dockerfile built
successfully. Existing Docker credential settings were not changed.

The image was tested using the [documented container smoke command](../README.md#container),
with `--network none`, a read-only fixture mount and `--require-unprivileged`.
The image's installed API and CLI passed all smoke checks as UID 10001. Host Python
was 3.13.13; the image used Python 3.13.15 with the frozen server dependencies.
The build and runtime smoke are now both configured in CI; remote CI was not run
from this session.

For manual checks, the normal API entrypoint was published only at
`127.0.0.1:8766`. Health returned HTTP 200. Chrome rendered Swagger UI; submitting
DOI `10.7717/peerj.4375` returned HTTP 200, canonical work `W2741809807`, the
expected title, PeerJ venue, authors, abstract and source attribution. Direct HTTP
requests then verified live title selection, filtered incoming edges and HTTP 422
for depth 4. The container's logs showed completed application shutdown; it exited
zero without an out-of-memory kill. Temporary containers were removed after checks.

## Bounded live OpenAlex observations

Official [authentication](https://help.openalex.org/api/authentication/),
[singleton lookup](https://help.openalex.org/api/get-single-entities/),
[search](https://help.openalex.org/api/searching/),
[pagination](https://help.openalex.org/api/paging/) and
[citation recipes](https://help.openalex.org/how-to/api-recipes/) were rechecked.
No adapter change was needed. Title-specific filter search remains documented but
deprecated; replacing it with general search would also search abstracts/full text.

No API key was supplied to these smoke requests. DOI resolution returned
`W2741809807`. Title search for “The state of OA” returned two distinguishable
candidates and status `more`; the published PeerJ DOI was explicitly selected.
Search was bounded to two candidates per page, four considered results, two
requests and 15 seconds, with retries disabled.

All live graph modes used depth 1, at most four nodes, six edges, four requests and
20 seconds, with retries disabled and `min_citations=0` applied after traversal.

| Mode | Returned nodes / edges | Physical requests | Outcome |
| --- | --- | --- | --- |
| Outgoing | 4 / 3 | 4 | `truncated`, reason `nodes` |
| Incoming | 4 / 3 | 2 | `truncated`, reason `nodes` |
| Both | 4 / 3 | 4 | `truncated`, reason `nodes` |

Returned assertions were checked against citing records' `referenced_works`.
Examples were `W2741809807 → W1560783210` and
`W3137875885 → W2741809807`; evidence identified the citing provider record and its
source URL with reported status. The normal container separately returned a
three-node/two-edge incoming graph truncated at its smaller node bound.
These are successful bounded results, not exhaustive citation neighborhoods.

## Remaining limitations

No correctness blocker was found in the exercised paths. No runtime API,
dependency or database migration changed in these follow-ups. No release,
deployment or publication was performed.

Two dependency deprecation warnings remain in the FastAPI/Starlette test-client
path (httpx compatibility and an AnyIO alias). They were not suppressed. The
Docker credential-helper workaround is local; regular authenticated pulls were
not repaired or tested. Live smoke did not cover every provider error, authenticated
access, complete live pagination or live traversal at depths 2–3; those behaviors
have deterministic offline coverage where applicable.

Provider order and records can change. Filters cover acquired records only; exact
names do not disambiguate authors. Evidence links identify live records rather
than archived payloads. Health reports process liveness. Load testing and external
production deployment were not performed.
