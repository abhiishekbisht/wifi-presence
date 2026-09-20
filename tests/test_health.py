"""
Unit and integration tests for service health check.
"""
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health_check_returns_200():
    """Verify that GET /health returns 200 OK with expected payload."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "wifi-presence"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data


def test_root_endpoint():
    """Verify that root / returns API metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "health_url" in data
    assert data["health_url"] == "/health"
