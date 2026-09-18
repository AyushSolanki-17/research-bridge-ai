# Contributing

## Change workflow

1. Follow the [development setup](docs/development.md#setup) and run `make check`
   to establish a baseline. Use the [source map](src/research_bridge/README.md) to
   locate the behavior and its tests.
2. State the requested behavior, owner, acceptance criteria and smallest useful
   slice. Read the capability contract and [extension guide](docs/extending.md).
3. Add or update focused behavioral checks, implement the slice and inspect its
   diff. Keep business rules with their owner and compose dependencies at entrypoints.
4. Run `make check`, `make install-check` and `make smoke` for executable changes.
   Use the container check for container changes. Document commands actually run,
   remaining limits and any public compatibility impact.
5. Review naming, Google-style documentation, unnecessary abstractions and changed
   contracts. Submit a focused PR using the repository template.

Human and agent contributions use the same workflow. Point coding tools to
[AGENTS.md](AGENTS.md); do not maintain divergent copies of its rules.

## Commit and review conventions

Use Conventional Commits for commits and PR titles, for example:

```text
feat(api): add a health endpoint
fix(papers): normalize DOI identifiers
refactor(api): simplify application assembly
```

Keep headers within 100 characters. Describe breaking changes with `!` and an explanation in the body. Commit style is a review convention; no custom hooks or history checker are required.

Before adding behavior, find its existing owner and reuse its contracts. Keep each business invariant in one place. Review duplication by meaning and responsibility; similar-looking code does not always need a shared abstraction. Prefer composition and cohesive objects where behavior or state warrants them. Follow [coding style](docs/coding-style.md) and [architecture](docs/architecture.md).

Run the checks in [README.md](README.md). In a PR, explain changed behavior, ownership, verification and any compatibility or migration impact. Maintain repository instructions and skills here, alongside the code they describe.

## Naming and documentation review

The [naming and documentation requirements](AGENTS.md#naming-and-documentation-requirements) are mandatory for all contributions, including branches, complete commit messages, PRs, source, filenames and documentation. Use behavior-based names, never roadmap labels or encoded planning identifiers. Follow [Google-style documentation requirements](docs/coding-style.md#docstrings-and-comments). Review both rules before completion; commit-format checks alone do not enforce them.
