# ingestion/openalex

OpenAlex acquisition and normalization into canonical research records. Provider payloads and SDKs stay in infrastructure; application code coordinates bounded, resumable ingestion through ports.

Use `domain/`, `application/`, `infrastructure/` and `interfaces/` when those responsibilities exist. Keep internals flexible; add Python modules and exports with behavior. This is a source module scaffold, not a standalone distribution.

Follow [architecture](../../../../docs/architecture.md).
