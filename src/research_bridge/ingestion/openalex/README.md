# ingestion/openalex

OpenAlex acquisition and normalization into canonical research records.
Provider payloads and SDKs stay in infrastructure; application code
coordinates bounded ingestion through narrow application-owned ports.

## Provider access (checked 2026-09-08)

Source: https://help.openalex.org/api/authentication/ and
https://help.openalex.org/api/get-single-entities/

- Base URL: ``https://api.openalex.org``.
- Singleton lookup: ``GET /works/{id}`` where ``{id}`` is an OpenAlex
  work ID (``W...``), a bare DOI (``10.xxxx/...``), ``doi:10.xxxx/...``,
  or ``https://doi.org/10.xxxx/...``. IDs are case-insensitive.
- Merged records return HTTP 301 to the canonical ID; clients follow
  redirects automatically and use the payload's canonical ``id``.
- Authentication is optional for casual use. A free API key raises the
  daily budget 10x. Provide via ``Authorization: Bearer <key>`` (preferred)
  or ``?api_key=<key>``. Key is read from ``OPENALEX_API_KEY`` and never
  logged or stored in fixtures.
- Rate limits: 100 requests/second and daily budget; ``429 Too Many
  Requests`` on limit. Respect ``Retry-After``.
- Data terms: OpenAlex data is made available under CC0 where applicable.
  See https://help.openalex.org/access/overview/ and
  https://openalex.org/OpenAlex_termsofservice.pdf. Attribute
  OpenAlex as the source; do not claim completeness over the scholarly
  corpus.

Configuration lives in ``infrastructure/settings.py`` via
``OpenAlexSettings.from_env()``. ``OPENALEX_BASE_URL``,
``OPENALEX_TIMEOUT`` (seconds), and ``OPENALEX_MAX_RETRIES`` are optional
overrides. All network calls have explicit timeouts and finite retries.

Timeout defaults to 10 seconds and must be finite, positive and at most 60
seconds. It bounds the entire request attempt, including redirects, as well as
HTTP I/O waits. Retries default to 3 and must be integers from 0 through 5.
Invalid settings fail immediately with `ValueError`, including environment
values. Redirects are followed even with an injected client; that client's
finite redirect limit applies (HTTPX defaults to 20). Each attempt includes
its redirects. Backoff is at most 2 seconds. Numeric and HTTP-date `Retry-After`
values are honored; waits longer than 2 seconds stop with
`ProviderRateLimitedError` rather than retrying early. Cancellation during
requests or backoff propagates. Injected clients remain owned by the caller.

## Payload handling

- Missing optional fields (title, publication date, venue, abstract,
  citation count, topics, authors, referenced works) preserve ``None`` or
  empty tuple; they are not invented or coerced to zero. A reported
  ``cited_by_count`` of ``0`` is kept as ``0``; only a missing key or
  ``null`` becomes ``None``.
- Abstracts are reconstructed only from a valid
  ``abstract_inverted_index`` (``dict[str, list[int]]`` with non-negative
  ints and no duplicate positions). Invalid or missing indexes yield
  ``None`` and never a synthetic abstract.
- Topics keep the provider-supplied ``score`` unchanged and are marked
  ``InferenceStatus.INFERRED_PROVIDER``. A missing score stays ``None`` and
  is never zero.
- Boolean, negative or nonnumeric citation counts become `None`. Topic scores
  must be finite numbers in [0, 1]; invalid scores become `None`. Boolean abstract
  positions are invalid. Other malformed optional metadata is omitted rather
  than promoted to reported facts.
- ``referenced_works`` entries that fail ``OpenAlexWorkId`` parsing are
  ignored; valid ones are normalized.

## Errors

The adapter distinguishes:

- ``InvalidIdentifierError`` (domain) for unsupported forms,
- ``PaperNotFoundError`` for HTTP 404,
- ``ProviderRateLimitedError`` for HTTP 429,
- ``ProviderTimeoutError`` for per-request timeout (or exhausted retries
  with timeout cause),
- ``ProviderMalformedResponseError`` for invalid JSON or unexpected shape,
- ``ProviderRetryExhaustedError`` after finite retries on transient
  failures,
- ``asyncio.CancelledError`` propagates immediately and stops further
  requests.

Provider JSON never becomes a canonical model.

Follow [architecture](../../../../docs/architecture.md).
