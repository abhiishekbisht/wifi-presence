"""
Tests for Event Ingestion and Rooms API endpoints.
"""
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.main import app
from database.db import get_db_connection

client = TestClient(app)


def test_post_valid_event():
    """Verify that posting a valid event persists to DB and returns 201."""
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "timestamp": now_iso,
        "ap_id": "AP_01",
        "device_id": "dev_test_abc123",
        "event": "connect",
        "rssi": -52,
    }

    response = client.post("/events", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["device_id"] == "dev_test_abc123"
    assert "event_id" in data
    assert "session_id" in data

    # Verify event stored in DB
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events WHERE event_id = ?", (data["event_id"],))
        row = cursor.fetchone()
        assert row is not None
        assert row["device_id"] == "dev_test_abc123"
        assert row["ap_id"] == "AP_01"
        assert row["event_type"] == "connect"
        assert row["rssi"] == -52

        # Verify device upserted
        cursor.execute("SELECT * FROM devices WHERE device_id = ?", ("dev_test_abc123",))
        dev_row = cursor.fetchone()
        assert dev_row is not None
    finally:
        conn.close()


def test_post_invalid_event_schema():
    """Verify that invalid schema returns 422 Unprocessable Entity."""
    bad_payload = {
        "ap_id": "AP_01",
        # missing timestamp, device_id, event, rssi
    }
    response = client.post("/events", json=bad_payload)
    assert response.status_code == 422


def test_get_rooms():
    """Verify that GET /rooms returns configured rooms with nested APs."""
    response = client.get("/rooms")
    assert response.status_code == 200
    rooms = response.json()
    assert len(rooms) >= 3

    room_names = [r["room_name"] for r in rooms]
    assert "Room 101" in room_names
    assert "Room 102" in room_names

    room_101 = next(r for r in rooms if r["room_id"] == "Room 101")
    assert len(room_101["access_points"]) >= 1
    assert room_101["access_points"][0]["ap_id"] == "AP_01"


def test_websocket_live_stream():
    """Verify that WebSocket clients receive broadcasted events from POST /events."""
    with client.websocket_connect("/live") as websocket:
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = {
            "timestamp": now_iso,
            "ap_id": "AP_01",
            "device_id": "dev_ws_test_99",
            "event": "connect",
            "rssi": -45,
        }

        # Post event via REST
        resp = client.post("/events", json=payload)
        assert resp.status_code == 201

        # Check WebSocket received the event broadcast
        msg = websocket.receive_json()
        assert msg["type"] == "event"
        assert msg["device_id"] == "dev_ws_test_99"
        assert msg["ap_id"] == "AP_01"
        assert msg["event"] == "connect"
        assert msg["rssi"] == -45

