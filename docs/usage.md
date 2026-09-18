# Use the library, CLI and HTTP API

Start with the [quickstart](../README.md#quickstart). The examples below use live
OpenAlex access. Run the [offline journey](development.md#development-loop) for a
credential-free development check with synthetic data.

## Resolve from the CLI or HTTP

```sh
uv run --frozen research-bridge resolve '10.7717/peerj.4375'
uv run --frozen research-bridge explore W2741809807 --depth 2 --max-nodes 50 --max-edges 200 --max-requests 100 --max-seconds 30
curl -X POST http://localhost:8000/v1/papers/resolve -H 'Content-Type: application/json' -d '{"identifier":"10.7717/peerj.4375"}'
```

Results are JSON on stdout. Resolution errors are JSON on stderr. CLI exit codes:
0 success, 2 invalid input/settings, 3 missing seed, 4 provider failure, 5 truncated
exploration, 130 cancellation. Failed or truncated exploration preserves its
available graph on stdout; inspect `status`, `stop_reasons` and `unresolved`.
Parser help and syntax errors use argparse's text output.

HTTP research operations are read-only POST requests without application
authentication. Omitted bounds use the library defaults. See the
[HTTP contract](../src/research_bridge/api/README.md) for responses and errors.

## Search by title and select a candidate

```sh
uv run research-bridge search 'The state of OA' --page-size 5
# Use next_page with the same query and limits to review another page:
uv run research-bridge search 'The state of OA' --page-size 5 --page 2
curl -X POST http://localhost:8000/v1/papers/search -H 'Content-Type: application/json' -d '{"query":"The state of OA","limits":{"page_size":5}}'
```

Review `candidates` using their titles, authors, dates and venues. Choose the intended
candidate's `paper.identifiers.openalex_id.value`, then pass that identifier to
`research-bridge explore IDENTIFIER` or `POST /v1/graphs/outgoing`. No candidate is
automatically selected. Invalid selections follow existing identifier error behavior.
A valid query with no matches succeeds with no candidates. Blank queries are rejected.

```python
import asyncio

from research_bridge.ingestion.openalex.infrastructure.openalex_adapter import OpenAlexPaperAdapter
from research_bridge.research.papers.application import SearchLimits, SearchPapers

candidates = asyncio.run(
    SearchPapers(OpenAlexPaperAdapter()).execute("The state of OA", SearchLimits(page_size=5))
)
for candidate in candidates.candidates:
    print(candidate.paper.identifiers.openalex_id.value, candidate.paper.title)
# After reviewing the output, use your chosen identifier with ExploreOutgoing.
```

Search returns `complete` at provider end, `more` with `next_page`, `truncated`
at an acquisition limit, or `failed` on provider errors. CLI codes are 0 for
complete/more, 5 for truncated and 4 for failed; partial candidates remain on stdout.
Cancellation exits 130 and stops requests. Search limits default to 10 candidates
per page, 100 total unique candidates, 20 physical requests and 30 seconds per call.
Later pages replay prior provider pages for deduplication, consuming the same call
budget. See [pagination and limit semantics](../src/research_bridge/research/papers/README.md#title-candidate-search).

## Resolve a paper with the library

The library returns canonical metadata and stable source evidence. This example
uses live OpenAlex access; the normal test suite remains offline. See
[provider configuration and limits](../src/research_bridge/ingestion/openalex/README.md).

```python
import asyncio

from research_bridge.ingestion.openalex.infrastructure.openalex_adapter import OpenAlexPaperAdapter
from research_bridge.research.papers.application.resolve_paper import ResolvePaper

result = asyncio.run(ResolvePaper(OpenAlexPaperAdapter()).execute("10.7717/peerj.4375"))
print(result.paper.title)
print(result.evidence.to_dict())
```

## Explore outgoing citations with the library

```python
from research_bridge.knowledge_graph.application import ExplorationLimits, ExploreOutgoing

graph = asyncio.run(
    ExploreOutgoing(OpenAlexPaperAdapter()).execute(
        result, ExplorationLimits(depth=2, max_nodes=50)
    )
)
print(graph.status, graph.stop_reasons)
```

This continues the resolution example using its ingested seed. Read the
[traversal, budget and partial-result contract](../src/research_bridge/knowledge_graph/README.md)
before interpreting graph completeness.

## Explore incoming or combined citations

```sh
uv run research-bridge explore W2741809807 --mode incoming --depth 2
uv run research-bridge explore W2741809807 --mode both --depth 3 --max-requests 100
curl -X POST http://localhost:8000/v1/graphs/explore -H 'Content-Type: application/json' -d '{"identifier":"W2741809807","mode":"both","limits":{"depth":2}}'
```

```python
from research_bridge.knowledge_graph.application import ExploreCitations, ExplorationLimits

graph = asyncio.run(
    ExploreCitations(OpenAlexPaperAdapter()).execute(
        "W2741809807", ExplorationLimits(depth=2), mode="both"
    )
)
print(graph.mode, graph.status, graph.unread_incoming_pages)
```

Modes are `outgoing` (default), `incoming` and `both`. Edges always point from
citing to referenced paper. Combined traversal processes outgoing references then
incoming pages at each expanded node, using one shared budget. Incoming page
failures preserve earlier records and identify the interrupted page. See the
[direction and pagination contract](../src/research_bridge/knowledge_graph/README.md#incoming-and-combined-traversal).
Existing `ExploreOutgoing` imports and `/v1/graphs/outgoing` remain supported.

## Filter results and inspect evidence

```sh
uv run research-bridge explore W2741809807 --mode both --depth 2 --year-from 2018 --year-to 2025 --min-citations 0 --topic 'Graph Theory' > graph.json
curl -X POST http://localhost:8000/v1/graphs/explore -H 'Content-Type: application/json' -d '{"identifier":"W2741809807","mode":"both","filters":{"year_from":2018,"max_citations":100,"venue":"Nature"}}'
```

Optional CLI flags also include `--author`, `--venue` and `--max-citations`.
Ranges are inclusive. Names match exactly, ignoring case and whitespace; all
supplied filters combine with AND. Missing metadata fails an active filter. Invalid
filter values use HTTP 422 or CLI exit 2 with error code `invalid_filters`.
These examples may retain only the seed when the acquired neighborhood has no
matches. Filters apply after traversal, within the requested depth and budgets;
they do not query the full corpus. The seed stays, and filtered edges require
retained endpoints. Inspect `filters`, `acquired_nodes`, `acquired_edges`, `limits`
and `status` before interpreting coverage. See the
[full filter semantics](../src/research_bridge/knowledge_graph/README.md#filter-returned-papers-and-inspect-evidence).

```python
from research_bridge.knowledge_graph.application import ExplorationFilters

graph = asyncio.run(
    ExploreCitations(OpenAlexPaperAdapter()).execute(
        "W2741809807",
        ExplorationLimits(depth=2),
        mode="both",
        filters=ExplorationFilters(year_from=2018, min_citations=0),
    )
)
for node in graph.nodes:
    print(node.paper.identifiers.openalex_id, node.paper.title, node.evidence.to_dict())
for edge in graph.edges:
    print(edge.source, edge.target, edge.referenced_id, edge.evidence.to_dict())
```

For CLI/HTTP JSON, select a paper from `nodes` by its canonical identifier and
inspect its metadata and source. For example, after saving the CLI result above:

```sh
jq '.nodes[] | select(.paper.identifiers.openalex_id.value == "W2741809807") | {paper, evidence}' graph.json
jq '.edges[] | {source, target, referenced_id, evidence}' graph.json
```

Every evidence record exposes its stable ID, provider record ID, source URL,
observation time and reported/inferred status. Follow `evidence.source_url` to
inspect the source record; it may have changed since observation. Citation evidence
supports the original reference assertion, including when the target was merged.
