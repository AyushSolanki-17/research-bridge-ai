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

### Resolve the remaining test-client dependency deprecation

**Owner:** root dependency manifest/lockfile and API test integration.
**Status:** blocked on a compatible upstream release at the last dependency review
(2026-09-17); the 2026-09-18 baseline reproduces the same warning.

Starlette 1.6.0 evaluates the deprecated `anyio.abc.BlockingPortal` alias. The
suite passes with the warning visible. The earlier httpx and pytest-asyncio
warnings were resolved; see [dependency evidence](verification.md#maintenance-verification-2026-09-17).

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
