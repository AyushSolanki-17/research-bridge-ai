"""Verify clean core wheel/source installations and installed consumer type information.

Run after building and verifying archive contents. Each artifact gets a fresh
virtual environment outside the checkout, constrained to the frozen core lockfile.
Dependency installation may access the network; the research journeys use loopback.
"""

import argparse
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str | Path, cwd: Path = ROOT) -> None:
    subprocess.run([str(arg) for arg in args], cwd=cwd, check=True)


def verify_installation(python_version: str, dist_dir: Path) -> None:
    """Exercise both installed artifacts without editable source or server packages.

    Args:
        python_version: Supported Python minor version to provision using uv.
        dist_dir: Directory containing the current project's built artifacts.

    Raises:
        subprocess.CalledProcessError: Installation, runtime or consumer typing fails.
        OSError: An artifact or required verification input cannot be read.
    """
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    stem = f"{project['name'].replace('-', '_')}-{project['version']}"
    with TemporaryDirectory(prefix="research-bridge-install-") as temporary:
        workspace = Path(temporary)
        constraints = workspace / "constraints.txt"
        _run(
            "uv",
            "export",
            "--frozen",
            "--no-dev",
            "--no-emit-project",
            "--no-hashes",
            "--output-file",
            constraints,
        )
        for kind, suffix in (("wheel", "-py3-none-any.whl"), ("source", ".tar.gz")):
            environment = workspace / kind
            _run("uv", "venv", environment, "--python", python_version)
            interpreter = environment / (
                "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
            )
            _run(
                "uv",
                "pip",
                "install",
                "--python",
                interpreter,
                "--constraint",
                constraints,
                dist_dir / f"{stem}{suffix}",
            )
            _run(
                interpreter,
                "-I",
                "-c",
                "import sys; print(sys.version); "
                "assert f'{sys.version_info.major}.{sys.version_info.minor}' "
                f"== {python_version!r}",
            )
            journey = ROOT / "tests/offline_journey.py"
            if kind == "source":
                with tarfile.open(dist_dir / f"{stem}{suffix}") as archive:
                    archive.extractall(workspace / "archive", filter="data")
                journey = workspace / "archive" / stem / "tests/offline_journey.py"
            _run(interpreter, "-I", journey, "--require-core-only", cwd=workspace)
            # Running the checker outside the checkout prevents source-tree fallback.
            consumer = workspace / "consumer.py"
            consumer.write_text((ROOT / "tests/typing/consumer.py").read_text())
            _run(
                sys.executable,
                "-m",
                "mypy",
                "--strict",
                "--no-incremental",
                "--python-version",
                python_version,
                "--python-executable",
                interpreter,
                consumer,
                cwd=workspace,
            )
            print(
                f"Verified {kind} installation and consumer types on Python {python_version}.",
                flush=True,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, choices=("3.13", "3.14"))
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    arguments = parser.parse_args()
    verify_installation(arguments.python, arguments.dist_dir.resolve())
