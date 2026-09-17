# Verification

Run the commands in [README](../README.md). The normal suite is offline and needs
no credentials. It covers identifier normalization, canonical metadata and evidence,
OpenAlex translation and bounded acquisition, title pagination and explicit selection,
outgoing/incoming/combined traversal, metadata filters and paper/source inspection,
and matching library/HTTP/CLI journeys. API health, schema drift,
side-effect-free library imports and static inward dependency rules are also checked.

For focused development, run the relevant capability tests, for example:

```sh
uv run --extra server pytest tests/research/papers tests/ingestion/openalex
uv run --extra server pytest tests/knowledge_graph tests/test_research_journeys.py
```

Use synthetic providers and HTTP transports for deterministic acquisition outcomes.
Inject monotonic clocks for elapsed boundaries and schedule cancellation without
wall-clock sleeps. Static checks do not prove runtime-import or cross-capability
correctness. Run the complete README checks before completing executable changes.

`test_complete_journey.py` runs the full search/selection/graph/filter/evidence path
through HTTP, the library and installed CLI processes with real adapter translation.
Its synthetic server and standalone library/CLI check live in `offline_journey.py`;
that file needs no pytest or web stack and is reused for the
[clean wheel and source installation checks](../README.md#checks-and-packaging).
CI runs these journeys and the offline suite on Python 3.13 and 3.14 with frozen
dependencies. Source-install checks use the journey extracted from the built
archive; isolated Python and core-only assertions prevent checkout/server imports.

`runtime_smoke.py` is an opt-in process smoke check, separate from pytest. It launches
the installed API command, exercises real HTTP sockets and the installed CLI,
then verifies completed SIGTERM shutdown. Run it on the host or inside the image
with networking disabled using the [container commands](../README.md#container).
It reuses the existing synthetic provider and evidence assertions.
