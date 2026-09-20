"""
Tests for Analytics, Attendance Dates, CSV Export, and Pilot Evaluation (Step 7).
"""
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.main import app
from tests.real_pilot_eval import evaluate_real_pilot

client = TestClient(app)


def test_get_analytics_endpoint():
    """Verify that GET /analytics returns structured historical analytics payload."""
    response = client.get("/analytics")
    assert response.status_code == 200
    data = response.json()

    assert "summary_kpis" in data
    assert "daily_trends" in data
    assert "room_utilization" in data
    assert "ap_activity" in data

    assert "total_events_logged" in data["summary_kpis"]
    assert "total_unique_devices" in data["summary_kpis"]


def test_attendance_by_date_and_csv_export():
    """Verify GET /attendance/{date} and GET /attendance/export/csv endpoints."""
    # 1. Check CSV export
    response = client.get("/attendance/export/csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    assert "record_id,room_id,room_name,capacity" in response.text

    # 2. Check attendance by date
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_resp = client.get(f"/attendance/{today}")
    assert date_resp.status_code == 200
    data = date_resp.json()
    assert data["date"] == today
    assert "records" in data


def test_real_pilot_eval_script():
    """Verify that Track B evaluation computes MAE, Precision, Recall, and F1."""
    eval_result = evaluate_real_pilot()
    assert "mae" in eval_result
    assert "precision" in eval_result
    assert "recall" in eval_result
    assert "f1" in eval_result
    assert eval_result["sessions_evaluated"] >= 3
    assert 0.0 <= eval_result["precision"] <= 1.0
    assert 0.0 <= eval_result["recall"] <= 1.0
