# Contributing

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
