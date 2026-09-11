# Verification

Run the commands in [README](../README.md). The normal suite is offline and needs
no credentials. It covers identifier normalization, canonical metadata and evidence,
OpenAlex translation and bounded acquisition, title pagination and explicit selection,
outgoing/incoming/combined traversal, and matching library/HTTP/CLI journeys. API health, schema drift,
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
