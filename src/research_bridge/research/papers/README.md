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

## Title candidate search

`SearchPapers(provider).execute(query, SearchLimits(), page=1)` returns attributed
`ResolvedPaper` candidates and never selects one. `PaperSearchPort` is separate
from singleton lookup so existing lookup providers need not implement search.
Select by passing a reviewed candidate's canonical work identifier to `ResolvePaper`
or `ExploreOutgoing`; no title-to-first-match conversion exists.

Whitespace is collapsed. Queries must contain 1–300 characters after normalization;
commas and pipes are rejected because they delimit provider filters. Remove these
punctuation characters when searching a title that contains them. Empty queries and
pages outside the allowed range raise `InvalidSearchError` before acquisition.

| Limit | Default | Hard maximum |
| --- | --- | --- |
| Candidates per public page | 10 | 100 |
| Unique candidates considered | 100 | 500 |
| Physical requests per call | 20 | 100 |
| Elapsed seconds per call | 30 | 120 |

Counts are positive integers; elapsed seconds must be finite and positive.
`page` is one-based and its starting offset must be below `max_results`. Each call
starts a fresh budget and replays the provider sequence from its first cursor.
This keeps the API stateless and deduplicates works by canonical OpenAlex ID before
slicing public pages. First occurrence wins; provider order is preserved. Replays,
retries, redirects and duplicate-only pages all consume acquisition allowance.
A request asks for no more records than the remaining candidate allowance.
Keep query and limits unchanged while following `next_page`.

- `complete`: the provider returned a null cursor. No matches or a page beyond
  provider end is complete with an empty candidate list. This is not corpus completeness.
- `more`: the requested page is filled and an unread cursor remains; `next_page`
  names the next review page. That page may be empty after deduplication.
- `truncated`: `results`, `requests`, `elapsed_time` or `repeated_cursor` stopped
  acquisition. Available candidates on the requested page remain inspectable.
- `failed`: `provider_failure`, with candidates from successful earlier pages retained.

`next_page` is null for complete, failed and truncated results. For a budget stop,
retry the same page with larger limits within hard maxima. Cancellation propagates
without more requests; partial candidates are not returned on cancellation.
The application cancels a pending provider page at the elapsed deadline and
retains candidates from earlier pages. The monotonic clock is injectable for
deterministic tests. Repeated cursors stop immediately; changing cursors with repeated/empty records still stop at budgets.
No snapshot is stored: provider changes between calls can shift page membership.
Clients reviewing changing results should also track identifiers already seen.

Candidates use the same metadata translation and stable paper evidence identity as
identifier resolution. Search ranking is provider-supplied, not an assertion of
identity or an inferred citation relationship.
