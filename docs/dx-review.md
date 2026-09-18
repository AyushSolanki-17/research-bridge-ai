# Developer experience review

Reviewed 2026-09-18. Scope: repository navigation, onboarding, extension paths,
capability boundaries, OOP/SOLID/DRY usage, offline testing, typed library consumption,
packaging, CI and shared agent instructions. This is an evidence-based repository
review, not a certification or comparison with other organizations.

The initial frozen suite passed 271 tests with one existing upstream deprecation
warning. Final commands and outcomes are recorded in
[verification evidence](verification.md#developer-experience-verification-2026-09-18).

## Findings and corrections

| Severity | Problem and consequence | Owner | Correction |
| --- | --- | --- | --- |
| MEDIUM | A 364-line root README mixed first-run instructions, usage and detailed verification, slowing navigation. | Root documentation | A shorter capability-oriented front page routes to usage, development and extension guides. |
| MEDIUM | The required task tracker contained more than 500 lines of largely completed work, increasing onboarding and agent context cost. | Contributor guidance | Current work is concise; dated acceptance records remain in implementation history. |
| MEDIUM | HTTP acquisition and pure metadata translation shared a 647-line module, making two distinct change paths harder to locate. | OpenAlex infrastructure | Translation has a cohesive module; acquisition paths reuse it. Adapter imports and public abstract reconstruction remain compatible. |
| MEDIUM | Static import checks enforced layers but missed reversed capability dependencies and concrete adapter imports by API routes. | Architecture tests | Tests now cover those boundaries and external HTTP/persistence dependencies in business layers, with positive and negative regression cases. |
| MEDIUM | Annotated source did not ship a `py.typed` marker, limiting installed consumers' type checking and editor assistance. | Distribution | Ship the marker, verify archive inclusion and check exact public result types against isolated installations. |
| MEDIUM | Local and CI checks repeated long install recipes and version-specific archive names, inviting drift during changes. | Development tooling and CI | Shared Make targets and an installation verifier derive artifact names from the manifest and exercise both distributions. |
| LOW | Contributors lacked a concise guide connecting a feature request to code, tests, contracts and composition. | Contributor documentation | Source map, worked change paths and a tool-independent handoff format reference the same AGENTS.md. |

No blocker or high-severity architecture defect was established in this review.
The medium findings describe concrete development friction or gaps in regression
protection, not observed corruption of research results.

## Sound decisions retained

- **Single responsibility:** identifiers, papers, attribution, filters and acquisition
  have distinct owners. The translator extraction separates a demonstrated concern.
- **Dependency inversion and interface segregation:** application-owned lookup,
  search and incoming protocols are injected into use cases. Concrete providers
  are composed by entrypoints, and tests substitute deterministic fakes.
- **Substitutability:** provider implementations must preserve budget accounting,
  cancellation, canonical values and failure semantics. Matching a method signature
  alone is insufficient; the existing journeys exercise these behavioral contracts.
- **OOP with composition:** validated immutable values protect inputs and results;
  `AcquisitionBudget` encapsulates mutable per-operation accounting. Stateless
  operations use functions without unnecessary service classes.
- **DRY by ownership:** HTTP, CLI and library share use cases. All provider paths
  share translation and retry policy. Transport-specific status mappings and
  distinct search/graph limit values retain their own semantics.
- **Proportional scope:** one distribution, optional server dependencies, no database,
  no provider registry and no extra package/build framework are needed today.

## Refactors deliberately avoided

Graph traversal remains one cohesive breadth-first algorithm with per-call state.
Splitting it into a strategy hierarchy would add indirection around ordering,
shared budgets and partial-result assembly without an additional supported algorithm.
The API and CLI remain small transport modules. No generic repository, base service,
factory framework or mandatory editor/agent plugin was added.

Supported library imports, CLI flags, HTTP shapes and research semantics are
preserved. The private payload translator moved; fault-injection tests target its
new owner. No database migration or dependency upgrade is involved.

## Limits and follow-up

The [upstream test-client warning](next-steps.md#resolve-the-remaining-test-client-dependency-deprecation)
remains visible. Static import enforcement cannot establish dynamic-import behavior
or every semantic contract. Existing OpenAlex identity requirements also mean a
second provider may require an intentional canonical-model change.

Archive and runtime verification establish fixture-scoped behavior, not provider
availability, corpus completeness or production load capacity. Remote CI and
container results must be reported separately from local checks. No release,
publication, deployment or live-provider regression test is implied by this review.
