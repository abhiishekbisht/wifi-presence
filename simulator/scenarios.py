"""
Predefined simulation scenarios for Wi-Fi Presence Estimation live demos and tests.
Scenarios:
  - normal_class: Standard attendance pattern (~80% occupancy in Room 101).
  - low_attendance: Sparse class (~25% occupancy in Room 101).
  - ap_failure: AP_01 goes offline for 10 minutes mid-session, triggering roam/drops.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from simulator.generator import WiFiEventSimulator



def get_scenario_plan(scenario_name: str, start_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """
    Generate event sequence for a named scenario.
    """
    sim = WiFiEventSimulator()
    start = start_time or datetime.now(timezone.utc)

    if scenario_name == "normal_class":
        # Room 101: 32 devices (80% capacity of 40)
        # Room 102: 25 devices (71% capacity of 35)
        # Lab 1: 18 devices (72% capacity of 25)
        targets = {
            "Room 101": 32,
            "Room 102": 25,
            "Lab 1": 18,
        }
        return sim.generate_event_plan(
            start_time=start,
            duration_minutes=60,
            attendance_targets=targets,
            ap_outages=None,
        )

    elif scenario_name == "low_attendance":
        # Room 101: 10 devices (25% capacity of 40)
        # Room 102: 8 devices
        # Lab 1: 6 devices
        targets = {
            "Room 101": 10,
            "Room 102": 8,
            "Lab 1": 6,
        }
        return sim.generate_event_plan(
            start_time=start,
            duration_minutes=60,
            attendance_targets=targets,
            ap_outages=None,
        )

    elif scenario_name == "ap_failure":
        # AP_01 goes offline between minute 15 and minute 25
        targets = {
            "Room 101": 30,
            "Room 102": 20,
            "Lab 1": 15,
        }
        outage_start = start + timedelta(minutes=15)
        outage_end = start + timedelta(minutes=25)
        outages = [
            {
                "ap_id": "AP_01",
                "start": outage_start,
                "end": outage_end,
                "reason": "Hardware / PoE failure",
            }
        ]
        return sim.generate_event_plan(
            start_time=start,
            duration_minutes=60,
            attendance_targets=targets,
            ap_outages=outages,
        )

    else:
        raise ValueError(f"Unknown scenario: {scenario_name}. Available: normal_class, low_attendance, ap_failure")


def run_scenario_batch(scenario_name: str, output_path: Optional[str] = None):
    """Run a scenario in batch mode and export to CSV."""
    sim = WiFiEventSimulator()
    start = datetime.now(timezone.utc)
    events = get_scenario_plan(scenario_name, start_time=start)

    import csv
    from simulator.generator import PROJECT_ROOT

    out = PROJECT_ROOT / (output_path or f"data/scenario_{scenario_name}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["timestamp", "ap_id", "device_id", "event", "rssi"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for ev in events:
            writer.writerow({k: ev[k] for k in fieldnames})

    print(f"Scenario '{scenario_name}' generated {len(events)} events -> {out}")
    return out


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run named simulator scenarios")
    parser.add_argument("scenario", choices=["normal_class", "low_attendance", "ap_failure"])
    args = parser.parse_args()

    run_scenario_batch(args.scenario)
