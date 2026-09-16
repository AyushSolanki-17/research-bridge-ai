# Product context

Research Bridge provides inspectable citation exploration for scholarly papers. The backend supports title search with candidate selection, identifier resolution, bounded incoming/outgoing citation neighborhoods at 1–3 hops, paper metadata, filters and source-attributed paper/edge records using OpenAlex.

## Research semantics

Implemented behavior: identifier resolution and bounded outgoing, incoming and combined citation
exploration and title search with explicit candidate selection through the library,
HTTP and CLI. Metadata filters apply after bounded traversal, retaining the seed
and only citations between retained papers. Paper and citation attribution stays
inspectable. Complete offline journeys cover
all directions and depths through the library, HTTP and CLI; clean installation
verification exercises the library and CLI without the optional server stack.
A separate bounded live smoke and manual container check passed on 2026-09-13;
see [verification evidence](verification.md). These observations do not guarantee
provider availability or corpus-wide coverage.

- Citation records show a reference relationship, not proven influence or causality.
- Preserve provider identifiers, source references and observation times. Distinguish reported facts from inference; unknown confidence is not zero.
- Support arbitrary seeds; “Attention Is All You Need” may be a demo input, never a special case in business logic.
- Report incomplete metadata, unresolved references and truncated exploration explicitly.
- Use small synthetic or appropriately licensed fixtures for offline tests. Verify provider access requirements and data terms when implementing live access.

## Scope

Deliver seed → citation graph → evidence inspection. No LLM, scoring or additional provider is required for this backend. Evaluate identifier normalization, citation direction, evidence traceability, deterministic traversal limits and error handling.
