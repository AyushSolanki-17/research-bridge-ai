"""Exercise installed server startup, HTTP journeys, CLI execution and shutdown.

This opt-in smoke check runs on the host or inside the built container. It uses
only a synthetic loopback provider and never imports the API into the test process.
"""

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryFile

import httpx
from offline_journey import TITLE, inspect_graph, provider_server, verify_library_cli


@contextmanager
def running_api(provider_url: str) -> Iterator[httpx.Client]:
    """Launch the installed server with fixture settings and verify clean shutdown.

    Args:
        provider_url: Local synthetic provider, independent of user credentials.

    Yields:
        HTTP client connected to the actual listening server.

    Raises:
        AssertionError: Startup fails or the process cannot shut down gracefully.
    """
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = {key: value for key, value in os.environ.items() if not key.startswith("OPENALEX_")}
    env.update(
        OPENALEX_BASE_URL=provider_url,
        OPENALEX_MAX_RETRIES="0",
        RB_HOST="127.0.0.1",
        RB_PORT=str(port),
        NO_PROXY="127.0.0.1",
    )
    with TemporaryFile(mode="w+t") as logs:
        process = subprocess.Popen(
            [str(Path(sys.executable).parent / "research-bridge-ai-api")],
            env=env,
            stdout=logs,
            stderr=logs,
        )
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", timeout=5, trust_env=False
            ) as client:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline and process.poll() is None:
                    try:
                        response = client.get("/health")
                        if response.status_code == 200:
                            break
                    except httpx.ConnectError:
                        pass
                    time.sleep(0.05)
                else:
                    logs.seek(0)
                    raise AssertionError(f"Server did not start: {logs.read()}")
                assert response.json() == {"status": "ok"}
                yield client
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                raise AssertionError("Server required forced termination") from None
        logs.seek(0)
        output = logs.read()
        # Uvicorn re-raises the captured SIGTERM after completing lifespan shutdown.
        assert process.returncode == -signal.SIGTERM, output
        assert "Application shutdown complete" in output, output
        assert "Traceback" not in output, output


def verify_http() -> None:
    """Check served docs/schema, search selection, all modes/depths and safe errors."""
    with provider_server() as provider_url, running_api(provider_url) as client:
        assert "swagger-ui" in client.get("/docs").text
        schema = client.get("/openapi.json")
        assert schema.status_code == 200
        assert set(schema.json()["paths"]) == {
            "/health",
            "/v1/papers/resolve",
            "/v1/papers/search",
            "/v1/graphs/explore",
            "/v1/graphs/outgoing",
        }
        first = client.post("/v1/papers/search", json={"query": TITLE, "limits": {"page_size": 1}})
        assert first.status_code == 200 and first.json()["status"] == "more"
        second = client.post(
            "/v1/papers/search",
            json={
                "query": TITLE,
                "limits": {"page_size": 1},
                "page": first.json()["next_page"],
            },
        )
        assert second.status_code == 200 and second.json()["status"] == "complete"
        selected = second.json()["candidates"][0]["paper"]["identifiers"]["openalex_id"]["value"]
        resolved = client.post("/v1/papers/resolve", json={"identifier": "doi:10.1234/W10"})
        assert resolved.status_code == 200
        assert resolved.json()["paper"]["identifiers"]["openalex_id"]["value"] == selected
        for mode in ("outgoing", "incoming", "both"):
            for depth in (1, 2, 3):
                response = client.post(
                    "/v1/graphs/explore",
                    json={
                        "identifier": selected,
                        "mode": mode,
                        "limits": {"depth": depth},
                        "filters": {"year_from": 2020, "topic": "Graph Theory"},
                    },
                )
                assert response.status_code == 200
                inspect_graph(response.json(), mode, depth)
        legacy = client.post("/v1/graphs/outgoing", json={"identifier": selected})
        assert legacy.status_code == 200 and legacy.json()["status"] == "complete"
        for identifier, limits, reason in [
            (selected, {"max_requests": 1}, "requests"),
            ("W30", {}, "unresolved_references"),
        ]:
            response = client.post(
                "/v1/graphs/explore",
                json={
                    "identifier": identifier,
                    "limits": limits,
                    "filters": {},
                },
            )
            assert response.status_code == 200 and response.json()["status"] == "truncated"
            assert response.json()["stop_reasons"] == [reason]
        for body in (
            {"identifier": "bad"},
            {"identifier": selected, "limits": {"depth": 4}},
            {"identifier": selected, "filters": {"year_from": 0}},
        ):
            response = client.post("/v1/graphs/explore", json=body)
            assert response.status_code == 422 and "error" in response.json()
        response = client.post(
            "/v1/graphs/explore", content="{", headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
        missing = client.post("/v1/papers/resolve", json={"identifier": "W404"})
        assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"
    with provider_server(fail_incoming=True) as provider_url, running_api(provider_url) as client:
        failed = client.post("/v1/graphs/explore", json={"identifier": "W10", "mode": "incoming"})
        assert failed.status_code == 502 and failed.json()["status"] == "failed"
        assert len(failed.json()["edges"]) == 1
        assert failed.json()["unread_incoming_pages"][0]["cursor"] == "unread"
        assert client.get("/health").json() == {"status": "ok"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-unprivileged", action="store_true")
    if parser.parse_args().require_unprivileged:
        assert os.getuid() != 0, "The container must run as an unprivileged user"
    verify_http()
    verify_library_cli()
    print(
        "Runtime smoke passed: real HTTP, docs, all modes/depths, CLI "
        f"and shutdown (uid={os.getuid()})."
    )
