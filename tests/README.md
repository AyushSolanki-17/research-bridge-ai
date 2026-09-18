# Verification

Run `make check` or the direct commands in the [development guide](../docs/development.md). The normal suite is offline and needs
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
wall-clock sleeps. Architecture tests enforce static layer direction and capability ownership, with
regression cases for permitted and forbidden imports. Dynamic imports and the
semantics of exported contracts still need review. Run the complete README checks before completing executable changes.

`test_complete_journey.py` runs the full search/selection/graph/filter/evidence path
through HTTP, the library and installed CLI processes with real adapter translation.
Its synthetic server and standalone library/CLI check live in `offline_journey.py`;
that file needs no pytest or web stack and is reused for the
[clean wheel and source installation checks](../docs/development.md#checks-and-packaging).
CI runs these journeys and the offline suite on Python 3.13 and 3.14 with frozen
dependencies. Source-install checks use the journey extracted from the built
archive; isolated Python and core-only assertions prevent checkout/server imports.

`runtime_smoke.py` is an opt-in process smoke check, separate from pytest. It launches
the installed API command, exercises real HTTP sockets and the installed CLI,
then verifies completed SIGTERM shutdown. Run it on the host or inside the image
with networking disabled using the [container commands](../docs/development.md#container).
It reuses the existing synthetic provider and evidence assertions.

`typing/consumer.py` is a static consumer fixture, not a pytest test. The installation
script copies it outside the checkout and checks exact result types against fresh
wheel/source environments. This verifies that the shipped `py.typed` marker and
supported exports work for consumers without installing the optional server stack.
