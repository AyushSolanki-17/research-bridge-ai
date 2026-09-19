# Source map

One typed, installable distribution. Importing `research_bridge` exposes its
version without loading the optional server stack or starting services. Begin with
[architecture](../../docs/architecture.md) and the [extension guide](../../docs/extending.md).

| Responsibility | Implementation | Tests and contract |
| --- | --- | --- |
| Parse canonical identifiers | [identifiers.py](research/papers/domain/identifiers.py) | [Identifier tests](../../tests/research/papers/test_identifiers.py), [papers contract](research/papers/README.md) |
| Paper metadata | [paper.py](research/papers/domain/paper.py) | [Translation tests](../../tests/ingestion/openalex/test_openalex_adapter.py) |
| Resolve and search | [Application exports](research/papers/application/__init__.py) | [Search tests](../../tests/research/papers/test_search_papers.py) |
| Request/deadline accounting | [acquisition.py](research/papers/application/acquisition.py) | [Budget tests](../../tests/ingestion/openalex/test_operation_budget.py) |
| Graph traversal and results | [explore.py](knowledge_graph/application/explore.py) | [Graph tests](../../tests/knowledge_graph/test_explore.py), [graph contract](knowledge_graph/README.md) |
| Incoming acquisition contract | [incoming.py](knowledge_graph/application/incoming.py) | [Incoming tests](../../tests/knowledge_graph/test_incoming.py) |
| Metadata predicates | [filters.py](knowledge_graph/application/filters.py) | [Filter tests](../../tests/knowledge_graph/test_filters.py) |
| Source evidence | [evidence.py](provenance/domain/evidence.py) | [Evidence tests](../../tests/provenance/test_evidence.py), [provenance contract](provenance/README.md) |
| HTTP acquisition | [openalex_adapter.py](ingestion/openalex/infrastructure/openalex_adapter.py) | [Acquisition tests](../../tests/ingestion/openalex/test_acquisition_limits.py), [provider contract](ingestion/openalex/README.md) |
| Payload translation | [translation.py](ingestion/openalex/infrastructure/translation.py) | [Malformed payload tests](../../tests/ingestion/openalex/test_payload_errors.py) |
| HTTP composition | [app.py](api/app.py) | [API contract](api/README.md) |
| HTTP schemas and routes | [research.py](api/research.py) | [Transport journeys](../../tests/test_research_journeys.py) |
| CLI composition and output | [cli.py](cli.py) | [Complete journeys](../../tests/test_complete_journey.py) |

Use the paper and graph application `__init__.py` exports for documented library
entrypoints. Domain values are shared across capabilities; provider code stays
inside ingestion. `py.typed` makes inline annotations available to installed consumers.
The root project owns packaging, tests and optional dependencies.
