# Backend verification evidence

## Maintenance verification 2026-09-17

Implemented the queued dependency, source-installation and Python compatibility
work after the initial review below. Existing documentation changes were retained.
No application code, HTTP contract, supported Python range or database schema changed.

### Dependency maintenance and remaining blocker

The original frozen baseline passed 244 tests with two warnings on Python 3.13.13.
An initial sandbox run could not bind the synthetic provider socket (232 passed,
2 failed, 10 errors); the permitted rerun passed without code changes. Dependency
downloads also required execution outside the network-restricted sandbox.

Added development-only `httpx2>=2.13,<3`, following the official
[Starlette test-client guidance](https://www.starlette.io/testclient/). The lockfile
adds httpx2 2.13.0, httpcore2 2.13.0, truststore 0.10.4 and the Emscripten-only
httpx2-jsfetch 1.0 dependency. The provider retains httpx 0.28.1; core and server
runtime dependencies are unchanged.

`uv lock --upgrade-package starlette` still resolves to Starlette 1.6.0. Its
[released test-client source](https://github.com/Kludex/starlette/blob/1.6.0/starlette/testclient.py#L53)
evaluates `anyio.abc.BlockingPortal`, which AnyIO 4.15.1 deprecates in favor of
`anyio.from_thread.BlockingPortal`. The
[release notes](https://starlette.dev/release-notes/) list no newer release at this
check. The alias is corrected on the upstream development branch, but no released
compatible upgrade was available. Both final suites retain this one warning.
The deprecation assignment remains incomplete pending an upstream release;
warnings were not suppressed, dependencies were not downgraded and vendored code
was not patched.

The initial Python 3.14 run passed but emitted 911 warnings: the Starlette alias
plus 910 calls to deprecated event-loop policy APIs in pytest-asyncio 0.26.0.
Updated the development constraint to `pytest-asyncio>=1.4,<2` and locked 1.4.0,
following its [compatibility changes](https://pytest-asyncio.readthedocs.io/en/stable/reference/changelog.html).
The suite uses no removed event-loop fixtures and needed no test changes. The
repeated runs removed all policy warnings, retaining only the Starlette warning.

### Python and distribution results

Used separate virtual environments with explicit `UV_PYTHON` and
`UV_PROJECT_ENVIRONMENT`; the printed/asserted versions were CPython 3.13.13 and
3.14.4 on macOS arm64. The [README commands](../README.md#checks-and-packaging)
match the configured CI checks; each `uv run` used `--frozen`. Mypy additionally
used `--python-version` for the selected interpreter. Pytest was run with `-q`.

| Check | Python 3.13.13 | Python 3.14.4 |
| --- | --- | --- |
| `uv sync --frozen --extra server --python VERSION` | Passed | Passed |
| Ruff lint and format checks | Passed; 70 formatted files | Passed; 70 formatted files |
| Strict mypy for selected Python target | Passed; 25 source files | Passed; 25 source files |
| Offline pytest suite | 244 passed, 1 upstream warning | 244 passed, 1 upstream warning |
| OpenAPI drift check | Passed | Passed |
| Fresh core wheel installation and isolated journey | Passed | Passed |
| Fresh source-archive installation and extracted isolated journey | Passed | Passed |

`uv build` built the source archive and wheel. `scripts/verify_distribution.py`
passed source parity, archive boundaries, metadata and documentation links for
77 source files and 29 wheel files. Each of the four final clean installations used
constraints from `uv export --frozen --no-dev --no-emit-project --no-hashes`.
Each journey ran with `-I --require-core-only`, asserted the package came from the
fresh environment, and executed that environment's installed CLI. The source
checks used `tests/offline_journey.py` extracted from the generated archive.
FastAPI, Starlette, Uvicorn and pytest were absent in all four environments.
Earlier unconstrained 3.13 wheel/source checks also passed; final constrained
checks used locked idna 3.19 rather than the newer 3.20 available from the index.

CI now selects and asserts both interpreter versions, keeps archive and wheel
checks, adds source installation, and runs the existing container build/smoke only
in the Python 3.13 entry. Ruby's YAML parser successfully read the workflow and its
two-version matrix; `git diff --check` passed. These are local results, not a remote
GitHub Actions result. Docker, process smoke, live OpenAlex, publication and
deployment were not rerun in this maintenance session.

### Code quality review

Reviewed the changed manifest, lockfile, CI and documentation, plus API/CLI
composition, identifiers, search, traversal, acquisition, filtering and evidence.
No BLOCKER or HIGH finding was identified in the inspected paths. Existing inward
dependency and side-effect-free import checks pass. Consumer-owned provider ports,
operation-scoped budgets, explicit partial results, post-traversal filters and
source-backed directed citations remain sound choices. No new service, abstraction
or application dependency was needed.

- **LOW — broad adapter exception handling:**
  [payload translation](../src/research_bridge/ingestion/openalex/infrastructure/openalex_adapter.py)
  catches `Exception` around identifier parsing and singleton translation. This
  can classify an internal programming defect as malformed provider data, while
  paginated translation has different catch behavior. The affected boundary is
  provider normalization/error reporting. A focused follow-up should catch the
  expected identifier exceptions and make malformed-payload handling consistent,
  with tests separating invalid input from unexpected defects. This pre-existing
  issue was reviewed without expanding the maintenance change into a refactor.
- **LOW — upstream test-client deprecation:** Starlette's alias warning remains
  the dependency-maintenance blocker described above. Adopt a compatible released
  fix and rerun both interpreter suites when it becomes available.

Changed content and the existing descriptive branch name were reviewed for naming,
documentation, optional dependency boundaries and scope. No handwritten Python was
changed. No migration or consumer API adjustment is required.

## Progress review 2026-09-17

Reviewed local commit `c0fe1ab` and the existing task, implementation and CI evidence.
This review updates documentation and assigns maintenance work; it does not
implement those assignments. Checks used the existing Python 3.13 environment
directly, without dependency changes or a fresh frozen installation.

| Check | Result |
| --- | --- |
| `.venv/bin/ruff check .` | Passed. |
| `.venv/bin/ruff format --check .` | Passed; 70 files already formatted. |
| `.venv/bin/mypy` | Passed for 25 source files. |
| `.venv/bin/python scripts/export_openapi.py --check` | Passed; no contract drift. |
| `.venv/bin/python -m pytest -q` | 244 passed; the same two dependency warnings remain. |

The initial sandboxed test run could not bind the synthetic provider's loopback
socket: 232 passed, 2 failed and 10 errored with `PermissionError`. The full suite
passed when rerun with permission outside that sandbox; no test or implementation
change was needed. The remaining warnings concern Starlette's httpx test-client
integration and the AnyIO `BlockingPortal` alias.

CI inspection found that source-distribution installation is not automated and
Python 3.14 is not exercised despite the declared `>=3.13,<3.15` support range.
These are the basis for the [next assignments](next-steps.md#next-assignments),
alongside dependency-warning maintenance. No Python 3.14 incompatibility is claimed.

Package builds, clean installations, process/container smoke checks, live OpenAlex,
remote CI, publication and deployment were not run during this review. The dated
results below remain the evidence for those earlier checks.

## Verification recorded 2026-09-13

Verified 2026-09-13 against the checkout at that time. The completed capability tasks were
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
