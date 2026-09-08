# Contributing

## Commits and pull requests

Use Conventional Commits for every new commit and PR title:

```text
feat(exploration): add bounded citation traversal
fix(evidence): preserve source attribution
refactor(graph): reuse path validation
feat(api)!: change pagination contract
```

Allowed lowercase types: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test`. Scope and `!` are optional. Scopes use lowercase letters, numbers, dots, underscores, slashes or hyphens. Headers must fit within 100 characters. Separate bodies and footers with a blank line. Breaking changes use `!` or a `BREAKING CHANGE:` / `BREAKING-CHANGE:` footer with an explanation. These casing and length limits are repository conventions layered on Conventional Commits 1.0.0.

Install the local hook once per clone (Python 3.10+ and Git required):

```sh
python3 scripts/install_hooks.py
```

The commit-msg hook rejects invalid messages. `Conventions / conventions` checks PR titles and every commit reachable from the proposed head, including merge/revert/bot commits. Rewrite fixup/squash placeholders before pushing. Keep squash commit titles conventional; if using merge commits, explicitly supply a conventional merge message. Existing historical exceptions are exact hashes with reasons in `.governance/legacy-commits.json`; never extend that list to bypass a new failure.

Local hooks can be bypassed and are not transferred by cloning. Hosted enforcement requires a protected default branch with the `conventions` status check required, direct pushes restricted, and no bypass actors. Review governance-file changes as policy changes. CI files cannot configure repository hosting settings by themselves.

## DRY and ownership

Before adding behavior, search for existing owners and contracts. State where the rule belongs, what existing behavior is reused, and why any new abstraction is needed. Use the existing capability's application API or a deliberately released library; do not copy an implementation into a second feature. Keep one authoritative place for each business invariant and API contract.

Apply DRY to knowledge and behavior, not superficial similarity. Keep adapters/transport translation with their owner; similar code with different semantics need not share an abstraction. Do not create a generic utility bucket or a separately published package merely to remove a few repeated lines. Add shared libraries only for demonstrated independent consumers. Generated clients must come from versioned schemas, never hand-copied DTOs.

```sh
python3 scripts/check_duplicates.py
```

The duplicate guard rejects exact code-token sequences of at least 100 tokens spanning 12 lines, including copies within one file. It scans application source, ignoring comments and whitespace. It excludes tests and documentation. Renamed logic, small repetitions, dynamic imports, and semantic duplication still require review. Do not lower thresholds or add exemptions to silence a new finding without an ownership/design review.

Instructions, skills and development tooling are maintained directly in this repository. Update their documentation and affected checks together. No parent checkout or template generator is needed. Generated API clients still come from pinned schemas.

Use README.md for runtime-specific checks. In a PR, explain changed behavior, ownership/reuse, verification, and compatibility or migration impact. A green duplicate scan is not proof that the architecture is DRY.
