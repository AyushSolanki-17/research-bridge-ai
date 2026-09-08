"""Verify built artifacts and import the wheel with no optional dependencies."""

import os
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    wheels = list((root / "dist").glob("*.whl"))
    sdists = list((root / "dist").glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit("Expected one wheel and one sdist; clean dist and run uv build")
    with zipfile.ZipFile(wheels[0]) as archive:
        names = archive.namelist()
        assert all(name.startswith(("research_bridge/", "research_bridge_core-")) for name in names)
        assert all(
            not name.endswith(".md") for name in names if name.startswith("research_bridge/")
        )
    with tarfile.open(sdists[0]) as archive:
        for name in archive.getnames():
            relative = Path(*Path(name).parts[1:])
            assert not any(
                part in {".git", ".agents", ".env", "PROJECT_CONTEXT.md"} for part in relative.parts
            )
    with tempfile.TemporaryDirectory(prefix="library-install-") as folder:
        env = Path(folder) / "venv"
        subprocess.run(["uv", "venv", "--python", "3.13", str(env)], check=True)
        python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--no-deps",
                "--no-index",
                str(wheels[0]),
            ],
            check=True,
        )
        subprocess.run(
            [
                str(python),
                "-I",
                "-c",
                "import importlib.util; import research_bridge; "
                "assert importlib.util.find_spec('fastapi') is None; "
                "assert research_bridge.__version__ == '0.1.0'",
            ],
            cwd=folder,
            check=True,
        )
    print("Built artifacts and dependency-free library import verified")


if __name__ == "__main__":
    main()
