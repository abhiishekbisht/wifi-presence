"""
Unit tests for DBSCAN Noise Filtering Module (Step 5).
"""
import pytest
from ml.noise_filter import filter_sessions_dbscan


def test_dbscan_filters_transient_walkbys():
    """
    Verify that DBSCAN classifies transient sessions (short duration, jittery RSSI)
    as noise, while stable sessions are classified as core or border.
    """
    # Create a batch of 12 sessions in a room: 10 seated (long, stable), 2 walk-bys (short, jittery)
    sessions = []

    # 10 genuine seated sessions
    for i in range(10):
        sessions.append({
            "device_id": f"dev_seated_{i}",
            "duration": 50.0 + (i % 5),  # 50-54 mins
            "avg_rssi": -48.0 - (i % 3),
            "rssi_std": 2.0 + (i * 0.2),  # 2.0 - 3.8 dBm
            "ap_transition_count": 0,
        })

    # 2 transient walk-by sessions
    sessions.append({
        "device_id": "dev_walkby_1",
        "duration": 0.2,  # 12 seconds
        "avg_rssi": -78.0,
        "rssi_std": 9.5,
        "ap_transition_count": 0,
    })
    sessions.append({
        "device_id": "dev_walkby_2",
        "duration": 0.3,  # 18 seconds
        "avg_rssi": -82.0,
        "rssi_std": 8.5,
        "ap_transition_count": 0,
    })

    enriched = filter_sessions_dbscan(sessions, eps=0.85, min_samples=3)

    assert len(enriched) == 12

    # Check walk-bys flagged as noise
    walkby_1 = next(s for s in enriched if s["device_id"] == "dev_walkby_1")
    walkby_2 = next(s for s in enriched if s["device_id"] == "dev_walkby_2")

    assert walkby_1["dbscan_label"] == "noise"
    assert walkby_1["dbscan_noise_flag"] == 1
    assert walkby_2["dbscan_label"] == "noise"
    assert walkby_2["dbscan_noise_flag"] == 1

    # Check seated devices are labeled core
    seated_cores = [s for s in enriched if s["device_id"].startswith("dev_seated_") and s["dbscan_label"] == "core"]
    assert len(seated_cores) >= 8


def test_dbscan_empty_and_small_batches():
    """Verify graceful handling for empty or sub-min_sample batches."""
    assert filter_sessions_dbscan([]) == []

    single = [{"device_id": "dev_single", "duration": 45.0, "avg_rssi": -50.0, "rssi_std": 2.0, "ap_transition_count": 0}]
    res = filter_sessions_dbscan(single, min_samples=3)
    assert len(res) == 1
    assert res[0]["dbscan_noise_flag"] == 0
