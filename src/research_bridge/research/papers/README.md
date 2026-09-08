# research/papers

Canonical scholarly works, identifiers and paper metadata. Add other research entities only when a query needs them.

`domain/identifiers.py` owns normalized DOI and OpenAlex work values and documents
accepted bare, prefixed and URL forms. Malformed work paths are rejected; direct
DOI construction also normalizes case. `domain/paper.py` owns immutable metadata.
`application/resolve_paper.py` exposes `ResolvePaper.execute(raw_identifier)`;
its injected `PaperProviderPort` returns `ResolvedPaper` with paper and evidence.
No provider payload or web framework enters this capability. See the
[library example](../../../../README.md#resolve-a-paper-with-the-library).

Follow [architecture](../../../../docs/architecture.md).
