---
name: production-readiness
description: Review release readiness, operational failures and evidence preservation.
---

# Production Readiness

Review the feature/system across the following dimensions.

## Correctness

- expected behavior tested
- edge cases handled
- invariants preserved
- failure behavior defined

## Security

- authentication
- authorization
- input validation
- secret handling
- injection risks
- SSRF where relevant
- unsafe file/network operations
- dependency exposure
- sensitive logging

## Reliability

- explicit timeouts
- bounded retries
- backoff
- idempotency
- concurrency limits
- graceful degradation
- cancellation behavior
- failure isolation

## Data

- migration safety
- transaction behavior
- consistency assumptions
- indexes
- backfills
- recovery strategy

## Performance

Look for:

- unbounded result sets
- unbounded graph expansion
- N+1 operations
- excessive external calls
- unnecessary serialization
- large in-memory materialization
- blocking operations in async paths

Avoid speculative optimization without evidence.

## Observability

Ensure operators can determine:

- what failed
- where
- for which operation/provider
- how often
- how long operations take

Check:

- structured logs
- traces
- metrics
- correlation context
- useful error classification

## Deployment

Consider:

- startup
- shutdown
- readiness
- liveness
- graceful termination
- configuration
- backwards compatibility
- rolling deployment compatibility
- rollback/forward recovery

## External providers

Check:

- timeout
- rate limits
- retry policy
- failure translation
- provider-specific assumptions
- degraded behavior

## Research Bridge semantics

Confirm production behavior does not silently lose:

- evidence
- provenance
- confidence
- source attribution
- inference status

## Final output

Report:

### Blockers

Issues that should prevent deployment.

### Important risks

Significant issues requiring conscious acceptance.

### Improvements

Non-blocking production improvements.

### Verified

Important production properties that were checked and appear sound.


## Ownership and reuse

Follow `CONTRIBUTING.md` for commit conventions and DRY review. Reuse the owning capability or released library before adding equivalent behavior. Keep generated contracts reproducible and maintain repository guidance locally.
