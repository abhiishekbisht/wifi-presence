"""
Tests for Occupancy Estimation and Attendance API endpoints (Step 5).
"""
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.main import app
from database.db import get_db_connection

client = TestClient(app)


def test_get_room_occupancy_endpoint():
    """Verify GET /rooms/{room_id}/occupancy returns structured occupancy metrics."""
    response = client.get("/rooms/Room 101/occupancy")
    assert response.status_code == 200
    data = response.json()

    assert data["room_id"] == "Room 101"
    assert data["room_name"] == "Room 101"
    assert data["capacity"] == 40
    assert "active_devices" in data
    assert "estimated_presence" in data
    assert "occupancy_pct" in data
    assert "confidence_avg" in data
    assert "present_device_ids" in data
    assert "timestamp" in data


def test_get_all_occupancy_endpoint():
    """Verify GET /occupancy returns a list of room occupancies."""
    response = client.get("/occupancy")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) >= 3

    room_ids = [r["room_id"] for r in data]
    assert "Room 101" in room_ids
    assert "Room 102" in room_ids
    assert "Lab 1" in room_ids


def test_invalid_room_occupancy_returns_404():
    """Verify 404 error when querying non-existent room."""
    response = client.get("/rooms/NonExistentRoom99/occupancy")
    assert response.status_code == 404
