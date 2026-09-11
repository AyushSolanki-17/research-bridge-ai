# Citation Explorer tasks

Status: identifier resolution and bounded outgoing, incoming and combined citation exploration are implemented through the Python library, HTTP and CLI with canonical metadata and provenance. Title search with explicit selection is implemented; filtering remains unimplemented.

Read [repository instructions](../AGENTS.md), [product context](product.md), [architecture](architecture.md), [coding style](coding-style.md) and affected capability READMEs before implementation.

Implement these tasks in order; each depends on the preceding task's verified output. Filtering and evidence inspection is next; the complete-journey task remains unassigned and not started. Record assignee, status, acceptance evidence, actual check results and limitations under the descriptive task name as work proceeds. List numbers only order this document; use capability names in code, files, branches and commits.

The deliverable is seed → bounded citation graph → evidence through the library, HTTP and CLI. Visual graph interaction is outside this repository. No bulk corpus ingestion, durable database, additional provider, LLM or scoring is required. Citation edges describe references, not proven influence. “Attention Is All You Need” is an optional demo seed, never a hardcoded special case.

1. **Ingest a paper by identifier**

   **Owner:** `research/papers`, `provenance`, `ingestion/openalex`.

   **Assignee:** Codex. **Status:** implemented and verified (2026-09-08).
   Offline evidence lives in `tests/research/papers`, `tests/provenance` and
   `tests/ingestion/openalex`: equivalent/invalid identifiers, two synthetic seeds,
   metadata translation, evidence round trips, actual redirects, bounded settings,
   rate limiting and cancellation. Live-provider availability is not a test gate.
   HTTP/CLI research commands and graph traversal are outside this completed slice.
   Verification: `uv run ruff check .`, `uv run ruff format --check .`,
   `uv run --extra server mypy`, `uv run --extra server pytest` (55 passed),
   `uv run --extra server python scripts/export_openapi.py --check` and `uv build`
   passed. A clean wheel installation resolved an offline work through the use
   case and adapter without FastAPI installed. Two dependency deprecation warnings
   remain; live acquisition and Docker were not tested.

   **After this task:** Given a DOI or OpenAlex work identifier, the library can fetch a paper and return normalized metadata with its source and observation time. Model only the values needed for this working ingestion slice.

   **Deliverable:** framework-independent identifiers, paper metadata and attribution values with one canonical owner each. Create only the modules needed for these behaviors.

   **Acceptance criteria**

   - Equivalent supported DOI forms and OpenAlex work identifier forms normalize consistently; malformed identifiers fail with specific errors. Document accepted forms.
   - Paper records preserve title, authors, publication date, venue, abstract when available, identifiers, citation counts and available topic metadata. Unknown values remain explicit rather than invented or converted to zero.
   - Attribution preserves provider name, provider record identity, an inspectable source reference and observation time. Evidence identifiers remain stable when records pass between ingestion, graph results and transports; document their identity semantics.
   - Provider payloads and framework types do not become canonical models. Reported citation facts are distinguishable from inference; unknown confidence is not zero.

   **Verification:** offline tests for equivalent/invalid identifiers, incomplete metadata, valid zero citation counts, attribution identity and serialization round trips where serialization is implemented.

   **Deliverable:** resolve an arbitrary supported identifier to a canonical paper with attribution using an injected provider boundary. Acquisition and payload translation belong to `ingestion/openalex`; canonical identity rules remain in `research/papers`.

   **Acceptance criteria**

   - Record current official OpenAlex access requirements, relevant data terms and the date checked before live integration. Configure any credentials through environment settings and keep them out of logs, fixtures and source.
   - Resolve DOI and OpenAlex inputs without paper-specific branches. A missing work is distinguishable from malformed input and upstream failure.
   - Translate supported metadata faithfully, including abstract reconstruction only when the payload supports it. Missing or malformed optional metadata has a documented outcome.
   - Apply explicit network timeouts and finite retry/request limits. Handle rate limits and transient failures without unbounded waiting; cancellation stops further acquisition.
   - Provider-specific types stay in infrastructure behind a narrow application-owned port. The normal test suite needs no credentials or network.

   **Verification:** deterministic adapter fixtures for successful resolution, missing work, sparse/malformed metadata, rate limiting, timeout, exhausted retries and cancellation. Include at least two distinct seeds to guard against demo-specific behavior.

2. **Explore outgoing citations within limits**

   **Owner:** `knowledge_graph`.

   **Assignee:** Codex. **Status:** implemented and verified (2026-09-08).
   Acceptance evidence: deterministic tests in `tests/knowledge_graph/test_explore.py`
   and `tests/ingestion/openalex/test_operation_budget.py`. These cover hop depth,
   cycles, deduplication, canonical merges, evidence, all count boundaries,
   controlled elapsed time, incomplete references, failures and cancellation.
   Numeric limits and exact completeness semantics are documented in the capability
   README. Provider ports now accept a shared acquisition budget; custom providers
   must account for every physical request. No database or migration is needed.
   Verification: Ruff lint/format, strict mypy, pytest (87 passed), OpenAPI drift
   check and wheel/sdist build passed. The suite remains offline; two existing
   dependency deprecation warnings remain. Live provider and Docker not tested.

   **After this task:** Given an ingested seed, the library can return the papers it cites across 1–3 hops, with directed edges, evidence and explicit limits or missing references.

   **Deliverable:** an in-memory outgoing citation neighborhood use case with source-attributed directed edges.

   **Acceptance criteria**

   - An edge always means citing paper → referenced paper. Every returned edge has evidence identifying the provider record and reference assertion that supports it.
   - Support depths 1, 2 and 3, with documented depth semantics, traversal order and deterministic tie-breaking for the same provider responses. Deduplicate nodes and edges and terminate on cycles.
   - Choose and document numeric defaults and hard maxima for depth, nodes, edges, provider requests and elapsed time before exposing exploration. Define whether the seed, pagination and retries consume each budget.
   - Enforce budgets across the whole operation, including retries and individual network waits. Tests use controlled time; deterministic budget behavior must not depend on wall-clock sleeps.
   - Distinguish complete, truncated and failed results, with machine-readable stop reasons. Complete means exhausted within the requested scope, not exhaustive coverage of the scholarly corpus.
   - Report unresolved references and incomplete metadata explicitly. Define partial-result behavior for provider failures and cancellation; never label incomplete acquisition as complete.

   **Verification:** synthetic graph tests for each hop depth, edge direction, duplicate records, cycles, unresolved targets, empty neighborhoods and exact boundaries of every budget. Assert both returned evidence and stop status.

3. **Expose resolution and exploration through HTTP and CLI**

   **Owner:** `api`, capability application contracts, `cli.py`.

   **Assignee:** Codex. **Status:** implemented and verified (2026-09-08).
   `POST /v1/papers/resolve`, `POST /v1/graphs/outgoing`, `research-bridge resolve`
   and `research-bridge explore` call the same library use cases. Offline journeys
   in `tests/test_research_journeys.py` compare metadata, evidence, graph limits,
   success, truncation and failures across callers. README examples and the OpenAPI
   snapshot describe actual contracts. No database migration or authentication
   dependency is introduced. Earlier process-health behavior is preserved.
   Verification: Ruff lint/format, strict mypy, pytest (109 passed), exported
   OpenAPI drift check and wheel/sdist build passed. A clean wheel installation
   without FastAPI imported the library and CLI, then ran actual CLI processes
   for resolution, complete/truncated exploration and invalid input against a
   local synthetic HTTP provider. Two existing dependency deprecation warnings
   remain. `docker build -t research-bridge-ai:local .` also passed. External
   OpenAlex was not tested; no deployment or container publication was performed.

   **After this task:** A caller can resolve an identifier, request an outgoing graph and inspect its evidence from a terminal or HTTP client, using the same library behavior.

   **Deliverable:** identifier resolution and outgoing exploration available through supported application exports, HTTP handlers in `api/` and CLI commands. API and CLI entrypoints wire concrete dependencies.

   **Acceptance criteria**

   - Library, HTTP and CLI invoke the same application behavior for resolution and exploration; transports do not duplicate normalization, traversal or attribution rules.
   - Requests expose documented defaults and bounded overrides. Invalid inputs and budgets, missing seeds and provider failures map to documented HTTP responses and CLI exit behavior.
   - Results expose canonical identifiers, metadata, citation direction, evidence, applied limits and completion/stop status. A caller can inspect the supporting source record for a returned edge.
   - Update the backend-owned OpenAPI snapshot with the implemented routes and schemas. Add runnable README examples for the actual CLI and HTTP syntax.
   - The library and CLI remain usable without the optional web stack; imports do not start a server or access the provider.

   **Verification:** library/API/CLI journeys against the same deterministic fake provider, including one success, one truncation and relevant error cases. Run schema drift and package build checks alongside the applicable README checks.

4. **Search by title and select a paper**

   **Owner:** `research/papers`, `ingestion/openalex`.

   **Assignee:** Codex. **Status:** implemented and verified (2026-09-09).
   Evidence: `tests/research/papers/test_search_papers.py` exercises ambiguous titles,
   explicit selection into outgoing exploration, no matches, cursor pagination,
   duplicate candidates, repeated cursors, exact result/request/time limits,
   cancellation, partial failure and library/HTTP/CLI contracts. The adapter reuses
   existing bounded HTTP acquisition. Public numbered pages replay and deduplicate
   the provider sequence; no server-side search session or database is introduced.
   Limitations: page membership can change with provider updates; commas and pipes
   in title queries are rejected. OpenAlex title-only filter search is documented
   but deprecated. Live provider acquisition has not been tested.
   Verification: `uv run ruff check .`, `uv run ruff format --check .`,
   `uv run --extra server mypy`, `uv run --extra server pytest` (140 passed),
   `uv run --extra server python scripts/export_openapi.py --check` and `uv build`
   passed. The exported search contract and wheel/sdist contents were reviewed.
   A clean wheel installation without FastAPI ran library and actual CLI search,
   explicit identifier selection and outgoing exploration against a local synthetic
   HTTP provider. Changed documentation links passed inspection. Two existing
   dependency deprecation warnings remain. Review also verified that injected CLI
   search bypasses unused OpenAlex configuration. Docker was not rerun for this change.

   **After this task:** A caller can enter a title, review paginated candidates, explicitly choose the intended paper and explore it.

   **Deliverable:** bounded, paginated title candidate search and explicit selection through the library, HTTP and CLI.

   **Acceptance criteria**

   - Search returns candidates with stable identifiers and enough available metadata to distinguish works, including title, authors, date and venue. It never silently selects a paper on the caller's behalf.
   - A caller can select a returned identifier and run the existing exploration use case. Empty queries, no matches and invalid selection inputs have documented outcomes.
   - Pagination exposes documented continuation/end semantics and respects result, request and time limits; repeated pages do not cause an infinite loop or duplicate candidate records.
   - Preserve attribution for each candidate. Update contracts and runnable examples with the new behavior.

   **Verification:** offline tests for ambiguous titles, explicit selection, no matches, multiple pages, duplicate candidates and search limit exhaustion. API and CLI demonstrate search → select → explore without hardcoding the demo title.

5. **Explore incoming and combined citations**

   **Owner:** `knowledge_graph`, `ingestion/openalex`.

   **Assignee:** Codex. **Status:** implemented and verified (2026-09-10).
   `ExploreCitations`, `POST /v1/graphs/explore` and CLI `explore --mode` expose
   outgoing, incoming and combined traversal. OpenAlex incoming acquisition uses
   cursor-paginated `cites` filtering and shared bounded HTTP handling. All modes
   retain citing-to-referenced edges with explicit source assertions. Existing
   outgoing entrypoints remain compatible; responses add mode and interrupted
   incoming-page context. No dependency or database migration is introduced.

   Evidence: `tests/knowledge_graph/test_incoming.py` covers asymmetric graphs at
   every supported depth/mode, pagination, cycles, duplicate records, repeated
   cursors, exact count and elapsed boundaries, shared budgets, cancellation,
   partial failures, malformed pages, physical retry accounting and transport
   agreement. Ruff lint/format, strict mypy, pytest (177 passed), OpenAPI drift
   check and wheel/sdist build passed. A clean wheel installation without FastAPI
   ran library and actual CLI acquisition against a local synthetic HTTP server
   for all modes at depth 3, including CLI truncation. Source, generated schema,
   package member paths and changed documentation links were reviewed.

   Limits: provider ordering and membership can change between calls. Missing or
   contradictory incoming reference assertions fail with partial data; merged
   reference identifiers that do not match the queried target are not inferred.
   Outgoing work precedes incoming pages at each expanded node and can exhaust
   the shared budget first. Live OpenAlex and Docker were not tested for this
   change. Two existing dependency deprecation warnings remain.

   **After this task:** A caller can explore papers citing the seed, papers the seed cites, or both, while retaining correct citation direction and shared limits.

   **Deliverable:** provider-backed incoming citation lookup and `incoming`, `outgoing` and `both` exploration modes across the supported 1–3 hops.

   **Acceptance criteria**

   - Incoming lookup acquires citing works using the provider's supported operation and pagination. It does not infer incoming completeness from an outgoing-only sample.
   - Stored and returned edge direction remains citing → referenced regardless of traversal mode. Each incoming edge preserves the source assertion used to establish it.
   - All modes reuse deduplication, evidence and completion semantics. Combined traversal shares one operation budget across both directions, all pages and retries.
   - Document how directions share the budget and how traversal order affects bounded coverage. Surface unread pages, unresolved references and exhausted budgets as incomplete exploration.
   - Library, HTTP, CLI and the exported schema expose the same modes and status semantics.

   **Verification:** asymmetric synthetic graphs that catch reversed edges or falsely inferred incoming links; all three modes at depths 1–3; paginated incoming results; cycles and combined-budget exhaustion. Verify an upstream failure after a successful page preserves truthful partial-result status.

6. **Filter results and inspect evidence**

   **Owner:** `knowledge_graph`, `research/papers`, `provenance`.

   **Assignee:** Unassigned. **Status:** ready for implementation.
   Incoming and combined exploration is verified. Use its shared traversal and
   evidence contracts when defining filter behavior and inspection journeys.

   **After this task:** A caller can narrow the neighborhood by available metadata and inspect each returned paper and the source supporting each citation.

   **Deliverable:** year, author, venue, citation-count and topic filters, plus paper and source inspection for returned results.

   **Acceptance criteria**

   - Document filter input forms, range boundaries, combination rules and missing-value behavior. Use available provider metadata; missing topics or venues are not inferred.
   - Choose and document whether filters affect traversal expansion or only returned results. Report applied filters and bounded scope so users cannot mistake the result for a corpus-wide query.
   - Define seed retention and endpoint handling for filtered edges. Returned edges reference inspectable endpoints; filtering never creates misleading or unsupported citation relationships.
   - A selected returned paper exposes its available metadata and attribution. Every returned citation exposes its evidence identifier, provider record/source reference and observation time without requiring access to raw internal objects.
   - Carry the same filters and inspection data through library, HTTP and CLI, with matching OpenAPI and example updates.

   **Verification:** offline tests for each filter, combinations, boundary values, missing metadata and filter/traversal interaction. Journey assertions follow returned paper and edge evidence back to the supporting fixture records.

7. **Verify the complete journey and installable package**

   **Owner:** API/CLI entrypoints and capability owners.

   **After this task:** A developer can install the built package and reproduce the documented complete journey, with offline checks proving behavior and limitations clearly recorded.

   **Deliverable:** a verified citation exploration backend with accurate usage documentation and recorded completion evidence.

   **Acceptance criteria**

   - Demonstrate title search → candidate selection → 1–3 hop incoming/outgoing/combined graph → filtered paper inspection → citation evidence through offline journeys. Include identifier entry as an alternative path and a seed other than the motivating demo.
   - Verify complete, truncated and failed outcomes, ambiguous seeds, unresolved references, pagination and exhausted budgets. Do not use live-provider availability as the normal test gate.
   - Export and check the final OpenAPI snapshot. Build the root wheel/sdist and verify a clean installation and documented application imports without FastAPI or unrelated optional dependencies.
   - Update README, product/architecture status and this tracker to reflect implemented behavior and remaining limitations. Record actual test commands/results; a live smoke test is optional and reported separately.
   - Review the full task diff for ownership, duplicated rules, unnecessary abstractions, unsupported completeness claims and content outside this repository's documented scope. Review generated schema and package contents as well as source.

   **Verification:** run all commands in [README checks and packaging](../README.md#checks-and-packaging). Inspect changed documentation links. Record failures rather than weakening checks.

Completion requires all seven tasks to meet their acceptance criteria, the complete offline journey and required README checks to pass, and documentation to reflect actual behavior. All citation directions are implemented; filters and complete-journey verification remain required. Report optional live smoke tests separately. Do not mark scaffolding as complete. Commits, publication and deployment require an explicit request.


## Implementation and developer-experience review

**Assignee:** Codex. **Status:** verified (2026-09-10).

Reviewed the implemented identifier resolution, title search, outgoing exploration,
provider translation, attribution and transport boundaries. Fixed application-level
search deadlines for stalled providers, oversized optional topic scores failing
translation, and incomplete abstract positions being joined into misleading text.
Regression coverage includes lookup and search translation, deadline cancellation,
and retention of candidates acquired before the deadline. Google-style constructor,
budget and cancellation docstrings now clarify dependencies, side effects and errors;
stale capability and test guidance was corrected.

Validation: `uv run ruff check .`, `uv run ruff format --check .`,
`uv run --extra server mypy`, `uv run --extra server pytest -q` (146 passed),
`uv run --extra server python scripts/export_openapi.py --check` and `uv build`
passed. A clean wheel installation without FastAPI completed offline title search,
explicit selection and outgoing exploration; installed CLI help passed. Reviewed
the diff, wheel/sdist member paths and changed Markdown file-link targets.
The HTTP schema is unchanged and no migration is needed. Gapped abstracts now
remain unknown rather than exposing incomplete text as a reconstructed abstract.
Two existing dependency deprecation warnings remain. Live-provider acquisition and
Docker were not tested in this review. Incoming/combined exploration was subsequently
implemented as recorded above; filters and complete-journey verification remain unimplemented.
