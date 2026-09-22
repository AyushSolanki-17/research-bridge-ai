# Current work and known limitations

The citation explorer implements identifier resolution, title search with explicit
selection, bounded outgoing/incoming/combined traversal, metadata filtering and
source inspection through the Python library, HTTP and CLI.

Start development with the [development guide](development.md) and
[code extension guide](extending.md). Read [product semantics](product.md),
[architecture](architecture.md), [coding style](coding-style.md) and the affected
capability README before changing behavior. Historical acceptance criteria and
dated completions live in [implementation history](implementation-history.md).
Actual run evidence lives in [verification](verification.md).

## Next assignments

### Publish the citation explorer contract and package

**Owner:** root distribution, `contracts/`, API schema export and release workflow.
**Status:** ready. The research behavior and local acceptance checks are complete;
the package and schema are not yet published or versioned for a consumer.

**Outcome:** provide one immutable backend release that a frontend can pin without
reading this repository's source or copying its models. This is the critical path
for the first browser-based seed → graph → evidence journey. Do not add research
behavior while preparing the handoff.

**Smallest slice:**

1. Choose the first release identifier from a clean commit and export the existing
   OpenAPI schema without changing its research operations.
2. Publish or attach the schema with its SHA-256 checksum and build the matching
   wheel and source distribution. Record the package version, schema checksum and
   supported API base-path expectations in the public release notes.
3. Run `make check`, `make install-check` and `make smoke`, then require the existing
   remote CI job to pass for the exact release commit. Run the configured container
   smoke before publishing a container artifact.
4. Establish this schema as the compatibility baseline for later consumer upgrades.
   Future changes must preserve documented errors, evidence identifiers, bounds,
   pagination and partial-result semantics or be released as an intentional
   compatibility change.

**Acceptance:**

- The released schema describes health, paper resolution, title search, outgoing
  exploration and direction-selectable exploration exactly as implemented.
- The release handoff contains an immutable release identifier, schema location,
  SHA-256 checksum, package artifact locations and the verification results for the
  release commit.
- A clean consumer can install the core package without FastAPI, while the server
  extra and documented API command still run the same contract.
- `README.md`, `contracts/README.md` and verification evidence distinguish the
  published release from local development. Publication and tagging occur only
  with explicit release authorization.

**Non-goals:** new endpoints, persistence, authentication, scoring, an additional
provider or frontend-specific response shapes. The existing test-client warning is
maintenance work and does not block this release unless it becomes a failing check.

### Resolve the remaining test-client dependency deprecation

**Owner:** root dependency manifest/lockfile and API test integration.
**Status:** blocked on a compatible upstream release. The 2026-09-21 review
reproduced the warning and confirmed that a targeted Starlette lock refresh has no
released update to select.

Starlette 1.6.0 evaluates the deprecated `anyio.abc.BlockingPortal` alias. The
suite passes with the warning visible. The earlier httpx and pytest-asyncio
warnings were resolved; see [dependency evidence](verification.md#maintenance-verification-2026-09-17).
Starlette merged the upstream correction on 2026-09-05, but its latest PyPI release
remains 1.6.0 and predates that correction. See the
[current dependency review](verification.md#test-client-dependency-review-2026-09-21).

When revisiting this item, reproduce it under the frozen dependencies, check
current official upstream guidance, and attempt a targeted compatible update.
Acceptance: remove the warning's cause without suppression or weakened assertions,
preserve optional server dependencies and research contracts, and pass the code,
contract and installation checks on the default Python 3.13. Check Python 3.14
explicitly if the dependency change needs compatibility investigation. Record an
actual upstream blocker if no compatible release fixes it.

## Developer experience review

The [DX review](dx-review.md) records the audit findings, corrections and deliberate
design choices. It links the current verification evidence and remaining limits.
Use those findings when extending the code; completed capabilities do not need to
be implemented again.

## Scope and evidence

Citation edges describe references, not proven influence. Filters apply after
bounded traversal and do not search the entire corpus. Provider records and order
may change, and evidence links do not archive historical payloads. No durable
persistence, additional provider, LLM, scoring or visual graph UI is implemented.

For newly authorized work, record the concrete behavior, owner, acceptance criteria,
status, actual checks and remaining limits here. Move completed detail into the
history once verified. Use descriptive names rather than encoded planning labels.
