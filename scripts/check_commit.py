"""Check Conventional Commit messages with repository-specific historical exceptions."""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

HEADER = re.compile(
    r"(?:build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
    r"(?:\([a-z0-9][a-z0-9._/-]*\))?!?: \S.*"
)
ROOT = Path(__file__).resolve().parents[1]


def validate(message):
    lines = message.splitlines()
    if not lines or not HEADER.fullmatch(lines[0]):
        return "expected type(scope)!: description (scope and ! are optional)"
    if len(lines[0]) > 100 or lines[0] != lines[0].rstrip():
        return "header must be at most 100 characters with no trailing whitespace"
    if len(lines) > 1 and lines[1].strip():
        return "separate the header and body/footer with a blank line"
    for line in lines[2:]:
        if line.startswith(("BREAKING CHANGE:", "BREAKING-CHANGE:")):
            if not re.fullmatch(r"BREAKING(?: CHANGE|-CHANGE): \S.*", line):
                return "breaking-change footer needs a description"
    return None


def git(*args, **kwargs):
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
        **kwargs,
    ).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--message-file", type=Path)
    group.add_argument("--ci", action="store_true")
    group.add_argument("--history", action="store_true")
    args = parser.parse_args()
    if args.message_file:
        message = git("stripspace", "--strip-comments", input=args.message_file.read_text())
        error = validate(message)
        if error:
            raise SystemExit(f"Commit rejected: {error}")
        return
    event_path = os.environ.get("GITHUB_EVENT_PATH") if args.ci else None
    event = json.loads(Path(event_path).read_text()) if event_path else {}
    if event.get("deleted"):
        return
    pr = event.get("pull_request")
    if pr:
        error = validate(pr["title"])
        if error:
            raise SystemExit(f"PR title rejected: {error}")
        revision = pr["head"]["sha"]
    else:
        revision = event.get("after") or "HEAD"
    # Resolve hashes only; do not let input become git command options.
    revision = git("rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}").strip()
    policy = json.loads((ROOT / ".governance/legacy-commits.json").read_text())
    failures = []
    for sha in git("rev-list", revision).splitlines():
        if sha in policy:
            continue
        error = validate(git("show", "-s", "--format=%B", sha))
        if error:
            failures.append(f"{sha[:12]}: {error}")
    if failures:
        raise SystemExit("Non-conventional commits:\n" + "\n".join(failures))
    print("Conventional Commit history verified")


if __name__ == "__main__":
    main()
