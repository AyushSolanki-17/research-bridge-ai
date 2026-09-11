# Repository instructions

## Start here

Read [next steps](docs/next-steps.md), [coding style](docs/coding-style.md), [product context](docs/product.md), [architecture](docs/architecture.md), and the affected capability README. Architecture governs placement; product context governs research semantics. This repo implements identifier resolution, title candidate search and bounded outgoing, incoming and combined citation exploration through the library, HTTP and CLI. Metadata filters apply to returned results after bounded traversal. Read README.md for runnable checks and report only verification actually performed.

## Contribution policy

Read [CONTRIBUTING.md](CONTRIBUTING.md) for Conventional Commits and ownership/reuse review. Follow the same policy when writing commits as an agent. Repository instructions, skills and tooling are owned and edited in this clone; no external template synchronization is required.

## Naming and documentation requirements

Name work by its concrete capability or behavior. Never include roadmap phase numbers, phase labels, milestone/stage labels or encoded planning identifiers in commit messages (including bodies and footers), branch names, PR titles/bodies, code comments, docstrings, classes, functions, variables, files, directories, tests, fixtures, schemas, configuration, documentation or generated artifacts. Do not replace a phase label with a task/step number in those names. Plain numbered task lists are allowed for ordering work; refer to tasks by their descriptive names outside that list. Technical versions and genuine domain terminology are not roadmap labels.

Use names such as `feat/identifier-resolution`, `resolve_paper` and `fix(papers): normalize DOI identifiers`. Before completing work, inspect changed content and proposed branch/commit/PR metadata for violations and correct them. Do not rewrite existing Git history unless explicitly requested.

Google-style documentation is mandatory for new or changed handwritten code: Python uses Google docstrings; TypeScript/JavaScript uses Google's JSDoc conventions. Follow [coding style](docs/coding-style.md) for language-specific requirements. Comments explain intent, constraints and non-obvious decisions, not planning history or a narration of obvious code. Documentation and naming review is a completion requirement; existing automated checks do not prove compliance.

## Ownership and boundaries

Use `src/<namespace>/` business capability modules with `domain/`, `application/`, `infrastructure/`, and `interfaces/` as needed. All FastAPI code belongs in `src/research_bridge/api/`: app assembly, routers, HTTP schemas, dependencies, middleware and server startup. Business capabilities outside `api/` must not import the API package, FastAPI, Starlette or Uvicorn. API routes call framework-independent application contracts; `cli.py` provides the separate command-line entrypoint. Reserve `packages/` for independently reusable libraries.

Follow the explicit dependency rules in the architecture document. Avoid generic shared buckets, circular imports, speculative services and unused abstractions. Keep consistent boundaries with flexible internals: do not require every layer or template file in a small capability. Add dependencies and modules only with a concrete capability. Preserve provenance, typed relationships, source attribution and explicit inference status.

Keep repository content self-contained: source, docs, skills, examples, generated artifacts and release notes describe only the capabilities and dependencies documented here. Do not import surrounding workspace planning files or use parent-directory packaging/build contexts.

## Focused skills

Load only the workflow relevant to the task:

- [backend-feature](.agents/skills/backend-feature/SKILL.md): Implement a backend capability across its domain, use cases, adapters and entrypoints.
- [architecture-review](.agents/skills/architecture-review/SKILL.md): Review module dependencies, domain boundaries, research semantics and architectural complexity.
- [api-design](.agents/skills/api-design/SKILL.md): Design or change FastAPI endpoints and versioned API contracts.
- [persistence-change](.agents/skills/persistence-change/SKILL.md): Change persistence ports, queries, transactions, migrations and backfills.
- [package-extraction](.agents/skills/package-extraction/SKILL.md): Extract or evolve an installable independently reusable Python library and its consumer API.
- [production-readiness](.agents/skills/production-readiness/SKILL.md): Review release readiness, operational failures and evidence preservation.

## Keep design proportional

Use the simplest implementation that satisfies the current acceptance criteria. OOP, SOLID and design patterns guide decisions; they are not a quota of classes, interfaces or layers. Plain functions, direct calls and existing framework features are appropriate when sufficient.

Do not build for hypothetical future consumers, scale or unapproved capabilities. Add a dependency, abstraction, service, queue, cache, database or package only when the current task demonstrates a need that existing code cannot reasonably meet. Keep the justification brief and concrete.

Architecture documents describe ownership and dependency boundaries, not a checklist of directories to create. Create layers only when implemented behavior needs them. Do not proactively restructure working code, remove scaffolds, expand tooling or perform architectural cleanup unless requested or necessary for the requested behavior. Keep unrelated observations in the final report.

## Implementation discipline

- Before editing, state the requested behavior, existing owner, acceptance criteria and smallest useful slice. Read the affected code and tests. A plan is preparation, not a reason to stop before completing authorized work.
- Make design choices explicit: identify object responsibilities, the invariants or state they encapsulate, and how dependencies are composed. Explain the concrete need for any chosen pattern; use the examples in `docs/coding-style.md` to keep small endpoints proportional.
- Implement one coherent slice at a time. Inspect its diff and run focused behavioral checks before broadening it. Keep changes traceable to the task; do not add unrelated cleanup, future features or speculative dependencies.
- Every new abstraction must solve a concrete need in this slice. Prefer direct code and composition. Do not add generic repositories, base services, factories, plugin systems, event buses or empty layers merely to demonstrate patterns or OOP. Extract shared behavior after real repetition establishes a common invariant.
- After a repeated failure or two unsuccessful fixes to the same symptom, stop speculative edits. Reproduce the failure, inspect the relevant code and diagnostic output, state the likely cause, then test one targeted correction. Revert only your own disproven changes; preserve user work. If evidence remains insufficient, report the specific blocker instead of accumulating patches or claiming success.
- Never weaken assertions, skip failing checks, suppress type/lint errors, fabricate results or replace real behavior with hardcoded demo output to get a green result. Fix the cause; explain any independently justified configuration change.
- Before completion, review the diff for unused code, unnecessary indirection, duplicated rules, error handling and scope creep. Remove your abandoned approaches. Run the relevant README checks and report actual results, including failures and untested behavior.
- Stop when acceptance criteria are met and relevant checks pass. Do not continue polishing, redesigning, expanding the roadmap or rerunning unchanged passing checks without new evidence. Mark incomplete work honestly; do not present scaffolding as a working capability.

## Completion

With executable changes, run the relevant checks in README.md and keep them aligned with CI. Report behavior changed, verification actually performed, compatibility/migration impact and material unresolved risks. Do not manufacture green checks for unimplemented systems.
