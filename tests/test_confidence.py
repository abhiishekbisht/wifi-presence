"""
Unit tests for Room Mapping Calibration and Presence Confidence Scoring (Step 4).
"""
import pytest
from ml.room_mapping import RoomMapping
from ml.confidence import (
    calculate_presence_confidence,
    calculate_duration_score,
    calculate_ap_consistency_score,
    calculate_rssi_stability_score,
    DEFAULT_PRESENCE_CONFIDENCE_THRESHOLD,
    DEFAULT_MIN_PRESENCE_MINUTES,
)


def test_room_mapping_calibration_lookups():
    """Verify static room mapping lookups and capacity queries."""
    rm = RoomMapping()

    assert rm.get_room_for_ap("AP_01") == "Room 101"
    assert rm.get_room_for_ap("AP_02") == "Room 102"
    assert rm.get_room_for_ap("AP_03") == "Lab 1"
    assert rm.get_room_for_ap("NON_EXISTENT") is None

    assert "AP_01" in rm.get_aps_for_room("Room 101")
    assert rm.get_room_capacity("Room 101") == 40
    assert rm.get_room_capacity("Room 102") == 35
    assert rm.get_room_capacity("Lab 1") == 25


def test_confidence_long_stable_session():
    """Verify high confidence and presence for long, stable seated sessions."""
    result = calculate_presence_confidence(
        session_duration_minutes=55.0,
        ap_transition_count=0,
        rssi_std=2.2,
        dbscan_noise_flag=0,
    )

    # duration: 55/60 = 0.9167 * 0.4 = 0.3667
    # ap_consistency: 1.0 * 0.25 = 0.25
    # rssi_stability: (1 - 2.2/15) * 0.20 = 0.1706
    # noise: 1.0 * 0.15 = 0.15
    # total ~ 0.937
    assert result.confidence > 0.85
    assert result.is_present is True
    assert result.duration_score > 0.90
    assert result.ap_consistency_score == 1.0


def test_confidence_short_transient_walkby():
    """Verify low confidence and non-presence for 10-second transient sightings."""
    result = calculate_presence_confidence(
        session_duration_minutes=0.2,  # 12 seconds
        ap_transition_count=0,
        rssi_std=8.0,
        dbscan_noise_flag=1,  # Flagged by DBSCAN as noise
    )

    assert result.confidence < 0.40
    assert result.is_present is False
    assert any("Duration" in r for r in result.reasons)



def test_confidence_borderline_duration():
    """
    Verify that a session with high signal quality but insufficient duration (< 30 min)
    is marked not present.
    """
    result = calculate_presence_confidence(
        session_duration_minutes=25.0,  # Below 30 min threshold
        ap_transition_count=0,
        rssi_std=2.0,
        dbscan_noise_flag=0,
    )

    assert result.confidence >= DEFAULT_PRESENCE_CONFIDENCE_THRESHOLD  # High confidence
    assert result.is_present is False  # Fails min_presence_minutes criterion
    assert any("Duration 25.0m < min threshold" in r for r in result.reasons)


def test_confidence_roaming_wanderer():
    """Verify reduced confidence for roaming devices with multiple AP transitions."""
    result = calculate_presence_confidence(
        session_duration_minutes=50.0,
        ap_transition_count=4,  # Roamed between 4 APs
        rssi_std=10.0,
        dbscan_noise_flag=0,
    )

    # AP consistency score drops significantly: 1 / (1 + 4) = 0.20
    assert result.ap_consistency_score == 0.20
    assert result.confidence < result.duration_score  # Dragged down by roaming


def test_custom_threshold_and_weights():
    """Verify configurability of weights and presence thresholds."""
    result = calculate_presence_confidence(
        session_duration_minutes=20.0,
        min_presence_minutes=15.0,
        confidence_threshold=0.50,
        weight_duration=0.50,
        weight_ap_consistency=0.20,
        weight_rssi_stability=0.20,
        weight_dbscan_noise=0.10,
    )

    assert result.is_present is True
