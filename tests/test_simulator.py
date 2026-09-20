"""
Unit tests for the Wi-Fi Event Simulator (Step 2).
"""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import pytest

from simulator.generator import WiFiEventSimulator, generate_salted_device_id
from simulator.scenarios import get_scenario_plan, run_scenario_batch


def test_salted_device_id_format_and_stability():
    """Verify that device IDs are salted hashes formatted as dev_<hex16> and deterministic for same inputs."""
    mac = "02:00:00:11:22:33"
    ssid = "CAMPUS_STUDENT_WIFI"
    salt = "test-salt"

    id1 = generate_salted_device_id(mac, ssid, salt)
    id2 = generate_salted_device_id(mac, ssid, salt)
    id3 = generate_salted_device_id(mac, "OTHER_WIFI", salt)

    assert id1.startswith("dev_")
    assert len(id1) == 20  # "dev_" (4) + 16 hex chars
    assert id1 == id2  # Stable per-SSID
    assert id1 != id3  # Different for different SSID


def test_batch_generation_event_schema(tmp_path: Path):
    """Verify generated batch events conform to PRD Section 9 schema."""
    sim = WiFiEventSimulator()
    output_csv = tmp_path / "test_events.csv"
    events = sim.generate_batch_events(output_csv_path=output_csv, duration_minutes=30)

    assert len(events) > 0
    assert output_csv.exists()

    required_keys = {"timestamp", "ap_id", "device_id", "event", "rssi"}
    valid_event_types = {"connect", "heartbeat", "disconnect"}

    for ev in events:
        assert required_keys.issubset(ev.keys())
        assert ev["event"] in valid_event_types
        assert isinstance(ev["rssi"], int)
        assert -100 <= ev["rssi"] <= -20
        assert ev["device_id"].startswith("dev_")
        assert ev["ap_id"] in ["AP_01", "AP_02", "AP_03"]


def test_live_async_generator():
    """Verify the async generator yields schema-compliant events."""
    async def _run():
        sim = WiFiEventSimulator()
        emitted = []
        # Run a 2-minute simulation at high speed (200x) so it finishes in < 1 second
        async for ev in sim.generate_live_events(duration_minutes=2, speed_multiplier=200.0):
            emitted.append(ev)
            if len(emitted) >= 10:
                break
        return emitted

    emitted = asyncio.run(_run())
    assert len(emitted) == 10
    assert all("timestamp" in e and "event" in e for e in emitted)



def test_scenarios():
    """Verify all 3 named scenarios execute and produce expected event patterns."""
    start = datetime.now(timezone.utc)

    # 1. normal_class
    normal_events = get_scenario_plan("normal_class", start_time=start)
    assert len(normal_events) > 50

    # 2. low_attendance
    low_events = get_scenario_plan("low_attendance", start_time=start)
    assert len(low_events) > 0
    assert len(low_events) < len(normal_events)

    # 3. ap_failure
    ap_failure_events = get_scenario_plan("ap_failure", start_time=start)
    # Check that during minute 16 to 24, AP_01 has 0 events
    outage_ap01_events = [
        e for e in ap_failure_events
        if e["ap_id"] == "AP_01" and 15 * 60 <= (e["_dt"] - start).total_seconds() <= 25 * 60
    ]
    assert len(outage_ap01_events) == 0
