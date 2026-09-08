import subprocess
import sys


def test_library_import_does_not_load_server_stack() -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import research_bridge; "
            "assert 'fastapi' not in sys.modules; assert 'uvicorn' not in sys.modules",
        ],
        check=True,
    )
