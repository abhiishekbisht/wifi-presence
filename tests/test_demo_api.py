"""
Tests for Live Demo Control Endpoints and Dashboard Static Serving (Step 6).
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from database.db import get_db_connection

client = TestClient(app)


def test_serve_dashboard_root():
    """Verify that GET / returns the dashboard HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Wi-Fi Presence Operations Center" in response.text
    assert "occupancyChart" in response.text


def test_demo_simulate_entry():
    """Verify POST /demo/simulate-entry creates an event and session."""
    payload = {"room_id": "Room 101"}
    response = client.post("/demo/simulate-entry", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "simulate_entry"
    assert data["room_id"] == "Room 101"
    assert "device_id" in data
    assert data["event_result"]["status"] == "success"


def test_demo_simulate_exit():
    """Verify POST /demo/simulate-exit emits a disconnect event."""
    # First simulate an entry
    client.post("/demo/simulate-entry", json={"room_id": "Room 101"})

    # Then simulate exit
    response = client.post("/demo/simulate-exit", json={"room_id": "Room 101"})
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "simulate_exit"


def test_demo_toggle_ap():
    """Verify POST /demo/toggle-ap changes AP status in database."""
    # Toggle AP_01 to offline
    response = client.post("/demo/toggle-ap", json={"ap_id": "AP_01", "status": "offline"})
    assert response.status_code == 200
    data = response.json()
    assert data["current_status"] == "offline"

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM access_points WHERE ap_id = 'AP_01'")
        row = cursor.fetchone()
        assert row["status"] == "offline"
    finally:
        conn.close()

    # Toggle back to online
    response = client.post("/demo/toggle-ap", json={"ap_id": "AP_01", "status": "online"})
    assert response.status_code == 200
    assert response.json()["current_status"] == "online"


def test_demo_run_scenario_endpoint():
    """Verify POST /demo/run-scenario triggers background execution."""
    response = client.post("/demo/run-scenario", json={"scenario": "normal_class", "speed": 100.0})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "scenario_started"
    assert data["scenario"] == "normal_class"


def test_demo_run_invalid_scenario_returns_400():
    """Verify invalid scenario returns 400."""
    response = client.post("/demo/run-scenario", json={"scenario": "invalid_scenario_xyz"})
    assert response.status_code == 400
