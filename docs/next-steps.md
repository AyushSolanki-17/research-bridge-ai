# Next implementation: citation explorer

Read AGENTS.md, product.md, architecture.md and coding-style.md before changing code. The existing runtime provides health, CLI version/help, packaging and checks; no research behavior is implemented. Implement this milestone in small working increments and keep this status accurate.

## Outcome

A caller can search by title and explicitly select a candidate, or resolve a paper by DOI/OpenAlex work identifier, explore bounded incoming and outgoing citation neighborhoods at 1–3 hops, inspect paper metadata, filter results and inspect the source attribution behind every returned citation. “Attention Is All You Need” is the motivating demo, with no hardcoded lineage. Start with identifier resolution and outgoing citations as the first slice; these alone do not complete the milestone.

## Implementation order

1. In research/papers, define canonical paper identifiers and metadata with explicit missing values. In provenance, define source attribution including provider record identity and observation time. Normalize equivalent identifiers and validate inputs. Preserve title, authors, publication date, venue, abstract when available, identifiers, citation counts and available topic metadata; missing data stays explicit.
2. In ingestion/openalex, add a provider adapter behind a narrow application-owned port. Verify current official OpenAlex access requirements before live integration; keep any credentials in environment configuration. Translate provider payloads, reconstruct metadata only when supported, handle missing works, rate limits and upstream failures with bounded retries/timeouts. Add paginated title candidate search and incoming-citation lookup as separate supported operations; do not infer reverse citations from an outgoing-only sample.
3. In knowledge_graph, represent directed cites edges (citing work → referenced work), deduplicate nodes/edges and implement deterministic traversal with depth, node, edge, request and time budgets. Handle cycles, unresolved targets, cancellation and partial results; return the reason exploration stopped. Support incoming, outgoing and combined traversal without reversing the stored cites edge. Start with an in-memory adapter; add durable storage only when required.
4. Expose the same use cases through capability-owned HTTP and CLI handlers, wired in bootstrap. Choose and document explicit safe defaults and hard maximum budgets. Return stable identifiers, edge direction, source attribution and completion status. Map invalid input, not found and provider failures consistently.
5. Add year, author, venue, citation-count and topic filters where source metadata supports them. Specify missing-value handling and whether filtering affects returned results or traversal expansion; do not silently imply corpus-wide coverage from a bounded neighborhood. Keep the UI able to inspect a selected paper and its source records.
6. Export the backend-owned OpenAPI snapshot and document runnable examples. Keep library imports independent of the optional web stack.

## Acceptance

Offline tests cover DOI/identifier normalization, ambiguous title candidates and explicit selection, incoming/outgoing edge direction, 1–3 hop traversal, duplicate records, cycles, exact budget boundaries, filters and missing values, missing metadata/references, provider pagination/timeout/rate-limit behavior and evidence traceability. API and CLI exercise the same use case with a deterministic fake provider. Results must distinguish complete, truncated and failed exploration. A live smoke test is optional and reported separately.

Run the lint, format, type, pytest, OpenAPI drift, build and clean-distribution checks in README.md. Explain ownership, meaningful design choices and remaining limitations. Do not publish packages or deploy as part of implementation unless requested.
