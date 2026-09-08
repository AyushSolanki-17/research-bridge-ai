# Product context

Research Bridge provides inspectable citation exploration for scholarly papers. The current milestone is title search with candidate selection, identifier resolution, bounded incoming/outgoing citation neighborhoods at 1–3 hops, paper metadata, filters and source-attributed paper/edge records using OpenAlex.

## Research semantics

- Citation records show a reference relationship, not proven influence or causality.
- Preserve provider identifiers, source references and observation times. Distinguish reported facts from inference; unknown confidence is not zero.
- Support arbitrary seeds; “Attention Is All You Need” may be a demo input, never a special case in business logic.
- Report incomplete metadata, unresolved references and truncated exploration explicitly.
- Use small synthetic or appropriately licensed fixtures for offline tests. Verify provider access requirements and data terms when implementing live access.

## Scope

Deliver seed → citation graph → evidence inspection. No LLM, scoring or additional provider is required for this milestone. Evaluate identifier normalization, citation direction, evidence traceability, deterministic traversal limits and error handling.
