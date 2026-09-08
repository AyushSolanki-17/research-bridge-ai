---
name: package-extraction
description: Extract or evolve an installable independently reusable Python library and its consumer API.
---

# Package Extraction

The goal is reusable capability, not maximum package count.

## Establish the reason

First verify an independent consumer and a stable API that cannot be served adequately by the root library’s exports. A potential extraction may provide:

- durable domain model
- reusable application engine
- independently optional integration
- independently consumed SDK

Do not create a package merely because a directory has many files.

## Public package requirements

Use standards-based `pyproject.toml` packaging.

Use a `src/` layout.

Ensure consumers install only dependencies genuinely required by the package.

Heavy/provider-specific dependencies should use separate adapters or optional dependency groups where appropriate.

## API design

Explicitly identify public symbols.

Keep internal modules private unless external consumers need them.

Public APIs should expose canonical concepts rather than implementation details.

Do not expose:

- FastAPI
- ORM entities
- sessions
- cloud SDK types
- provider SDK response objects

## Compatibility

Before moving or renaming exported symbols determine:

- existing internal consumers
- potential external consumers
- compatibility shim requirements
- deprecation strategy

## Isolation test

Ask:

> Can a fresh external Python project install this package and use its advertised capabilities without importing the Research Bridge API application or infrastructure stack?

If no, investigate why.

## Validation

Build the distribution.

Test the installed package rather than relying only on imports from the repository checkout.

Verify required package files are included in the resulting wheel/sdist.

Document the minimal consumer-facing usage.

## Default source convention

Keep ordinary business modules under the root `src/` namespace. A logical boundary or reusable internal module alone is insufficient for extraction. Create `packages/` only for a justified independently installable library with its own dependencies, build and compatibility lifecycle. The backend can expose supported use cases through one root distribution without extracting each capability.


## Ownership and reuse

Follow `CONTRIBUTING.md` for commit conventions and DRY review. Reuse the owning capability or released library before adding equivalent behavior. Keep generated contracts reproducible and maintain repository guidance locally.
