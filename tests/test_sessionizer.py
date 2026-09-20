"""
Tests for the Sessionizer Service (PRD Section 11 feature calculations and timeouts).
"""
from datetime import datetime, timedelta, timezone
from backend.services.sessionizer import Sessionizer
from database.db import get_db_connection


def test_session_lifecycle_and_features():
    """Verify session grouping, feature metrics, and database updates."""
    sessionizer = Sessionizer(inactivity_timeout_seconds=300)
    dev_id = "dev_session_test_1"
    t0 = datetime(2026, 9, 20, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Connect
    s_id1 = sessionizer.process_event({
        "device_id": dev_id,
        "ap_id": "AP_01",
        "event": "connect",
        "rssi": -50,
        "timestamp": t0.isoformat(),
    })
    assert s_id1 is not None

    # 2. Heartbeats (with RSSI variation and AP roaming)
    t1 = t0 + timedelta(minutes=5)
    sessionizer.process_event({
        "device_id": dev_id,
        "ap_id": "AP_01",
        "event": "heartbeat",
        "rssi": -52,
        "timestamp": t1.isoformat(),
    })

    t2 = t0 + timedelta(minutes=10)
    sessionizer.process_event({
        "device_id": dev_id,
        "ap_id": "AP_02",  # AP transition
        "event": "heartbeat",
        "rssi": -54,
        "timestamp": t2.isoformat(),
    })

    # 3. Disconnect
    t3 = t0 + timedelta(minutes=15)
    s_id_final = sessionizer.process_event({
        "device_id": dev_id,
        "ap_id": "AP_02",
        "event": "disconnect",
        "rssi": -56,
        "timestamp": t3.isoformat(),
    })
    assert s_id_final == s_id1

    # Check active session buffer closed
    assert dev_id not in sessionizer.active_sessions

    # Verify features saved to SQLite
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (s_id1,))
        row = cursor.fetchone()
        assert row is not None
        assert row["duration"] == 15.0
        assert row["connection_count"] == 4
        assert row["ap_transition_count"] == 1
        assert -54.0 <= row["avg_rssi"] <= -52.0
        assert row["rssi_std"] > 0.0
    finally:
        conn.close()


def test_inactivity_timeout():
    """Verify that a session is closed when time gap exceeds inactivity_timeout."""
    sessionizer = Sessionizer(inactivity_timeout_seconds=60)
    dev_id = "dev_timeout_test_1"
    t0 = datetime(2026, 9, 20, 10, 0, 0, tzinfo=timezone.utc)

    # Initial connect
    s_id = sessionizer.process_event({
        "device_id": dev_id,
        "ap_id": "AP_01",
        "event": "connect",
        "rssi": -48,
        "timestamp": t0.isoformat(),
    })

    # Event arriving 10 minutes later (well above 60s timeout)
    t_late = t0 + timedelta(minutes=10)
    s_id_new = sessionizer.process_event({
        "device_id": dev_id,
        "ap_id": "AP_01",
        "event": "connect",
        "rssi": -50,
        "timestamp": t_late.isoformat(),
    })

    # A new session should have been started
    assert s_id_new != s_id
