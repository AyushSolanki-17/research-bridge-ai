"""Verify the public health endpoint and API contract."""

from fastapi.testclient import TestClient

from research_bridge.api.app import create_app


def test_health_contract() -> None:
    """Verify liveness, its OpenAPI operation and unknown-route handling."""
    with TestClient(create_app()) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        schema = client.get("/openapi.json").json()
        assert schema["paths"]["/health"]["get"]["operationId"] == "get_health"
        assert client.get("/missing").status_code == 404
