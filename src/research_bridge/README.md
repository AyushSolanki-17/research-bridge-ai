# Source map

Research Bridge is one installable library with a framework-independent business
core and optional delivery integrations. Most consumers start with
`ResearchBridge` from the package root.

```text
research_bridge/
  bridge.py                 public business façade
  core/                     models, ports, rules, limits, and use cases
  providers/openalex/       HTTP acquisition and payload mapping
  api/                      optional FastAPI schemas, router, and standalone app
  cli.py                    command-line adapter over the same façade
```

| Responsibility | Implementation | Behavioral checks |
| --- | --- | --- |
| Public orchestration | [bridge.py](bridge.py) | [Embedded API](../../tests/api/test_embedding.py), [journeys](../../tests/test_research_journeys.py) |
| Identifiers | [core/identifiers.py](core/identifiers.py) | [Identifier tests](../../tests/core/test_identifiers.py) |
| Papers and evidence | [core/papers.py](core/papers.py), [core/evidence.py](core/evidence.py) | [Evidence tests](../../tests/core/test_evidence.py) |
| Provider contracts | [core/ports.py](core/ports.py) | Fake-provider tests throughout `tests/` |
| Resolution and search | [core/resolution.py](core/resolution.py), [core/search.py](core/search.py) | [Search tests](../../tests/core/test_search.py) |
| Citation contracts and traversal | [core/citations.py](core/citations.py), [core/explorer.py](core/explorer.py) | [Traversal tests](../../tests/core/test_explorer.py) |
| Filters and budgets | [core/filters.py](core/filters.py), [core/budget.py](core/budget.py) | Filter and acquisition-limit tests |
| OpenAlex integration | [OpenAlex provider](providers/openalex/README.md) | [Provider tests](../../tests/providers/openalex/test_client.py) |
| FastAPI integration | [API](api/README.md) | [Embedding test](../../tests/api/test_embedding.py), [transport journeys](../../tests/test_research_journeys.py) |
| CLI | [cli.py](cli.py) | Complete and transport journeys |

Dependency direction is deliberately small:

```text
api / cli ──> ResearchBridge ──> core ports and operations
    │                                  ▲
    └──────── providers/openalex ──────┘
```

`core/` and `bridge.py` never import transport or provider implementations.
`api/router.py` receives a configured `ResearchBridge`; only the standalone
`api/app.py` and CLI choose OpenAlex by default.
