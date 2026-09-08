"""Install repository-local commit hooks; preserve any different existing hook configuration."""

import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    actual = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"], text=True
    )
    if Path(actual.strip()).resolve() != root:
        raise SystemExit("Run hook setup from its own Git repository")
    configured = subprocess.run(
        ["git", "-C", str(root), "config", "--get", "core.hooksPath"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if configured and configured != ".githooks":
        raise SystemExit(
            f"Existing hooksPath {configured!r}: integrate hooks explicitly before changing it"
        )
    for path in (root / ".githooks").iterdir():
        path.chmod(path.stat().st_mode | 0o111)
    subprocess.run(
        ["git", "-C", str(root), "config", "--local", "core.hooksPath", ".githooks"],
        check=True,
    )
    print("Commit hooks enabled for this clone")


if __name__ == "__main__":
    main()
