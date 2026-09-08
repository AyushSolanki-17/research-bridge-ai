"""Launch the API server using environment host and port settings."""

import os


def main() -> None:
    import uvicorn

    uvicorn.run(
        "research_bridge.api.app:create_app",
        factory=True,
        host=os.getenv("RB_HOST", "127.0.0.1"),
        port=int(os.getenv("RB_PORT", "8000")),
    )
