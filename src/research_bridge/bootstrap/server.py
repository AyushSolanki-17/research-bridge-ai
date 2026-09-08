"""Local server entrypoint; configuration belongs to bootstrap."""

import os


def main() -> None:
    import uvicorn

    uvicorn.run(
        "research_bridge.bootstrap.api:create_app",
        factory=True,
        host=os.getenv("RB_HOST", "127.0.0.1"),
        port=int(os.getenv("RB_PORT", "8000")),
    )
