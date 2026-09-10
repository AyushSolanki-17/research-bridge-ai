# provenance

Evidence records, source attribution and confidence semantics. Evidence
references remain stable across ingestion, graph queries and answers.

## Evidence identity

Evidence identity is stable and does not include observation time.
Observation time is recorded but never changes the stable identifier.

- Paper record: ``openalex:work:<work-id>`` where ``<work-id>`` is the
  normalized OpenAlex work ID (e.g., ``W2741809807``).
- Citation assertion: ``openalex:citation:<citing-id>:<referenced-id>``
  (used by outgoing citation exploration).

Two observations of the same work at different ``observed_at`` times share
the same ``id``. Serialized form via ``Evidence.to_dict()`` round-trips
without identity loss; ``id``, ``provider``, ``provider_record_id`` and
``source_url`` remain constant while ``observed_at`` may differ.

## Attribution

Each ``Evidence`` preserves:

- ``provider`` (e.g., ``openalex``),
- ``provider_record_id`` (normalized work ID),
- ``source_url`` (inspectable ``https://openalex.org/<work-id>``),
- ``observed_at`` (timezone-aware UTC timestamp),
- ``inference_status`` (``REPORTED`` for the paper record; topics carry
  ``INFERRED_PROVIDER`` with their supplied score).

`domain/evidence.py` implements immutable evidence and serialization. Citation
identity helpers do not acquire citations or implement graph exploration.

Follow [architecture](../../../docs/architecture.md).
