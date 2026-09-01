"""ML service startup checks for the containerized demo."""

from fastapi.testclient import TestClient

from app.main import app


def test_ml_service_starts_and_reports_healthy() -> None:
    """Import all routes and verify the health endpoint is available."""
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
