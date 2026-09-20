"""
Live Simulator Runner.
Streams simulated events to the backend POST /events endpoint in real time.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import asyncio
import httpx
from datetime import datetime, timezone
from simulator.generator import WiFiEventSimulator
from simulator.scenarios import get_scenario_plan


async def forward_live_events(
    scenario_name: Optional[str] = None,
    duration_minutes: int = 60,
    speed_multiplier: float = 15.0,
    api_url: str = "http://localhost:8000/events",
):
    """
    Generate and forward live events to the FastAPI server.
    """
    sim = WiFiEventSimulator()
    start_time = datetime.now(timezone.utc)

    if scenario_name:
        events = get_scenario_plan(scenario_name, start_time=start_time)
        print(f"Loaded scenario '{scenario_name}' ({len(events)} events).")
    else:
        events = sim.generate_event_plan(start_time=start_time, duration_minutes=duration_minutes)
        print(f"Generated standard plan ({len(events)} events, duration: {duration_minutes}m).")

    print(f"Streaming to {api_url} at {speed_multiplier}x speed...")

    if not events:
        print("No events to stream.")
        return

    first_sim_dt = events[0]["_dt"]
    last_sim_dt = first_sim_dt

    async with httpx.AsyncClient(timeout=10.0) as client:
        sent_count = 0
        failed_count = 0

        for ev in events:
            curr_sim_dt = ev["_dt"]
            delta_sim_seconds = (curr_sim_dt - last_sim_dt).total_seconds()
            if delta_sim_seconds > 0:
                sleep_real_seconds = delta_sim_seconds / speed_multiplier
                await asyncio.sleep(sleep_real_seconds)
            last_sim_dt = curr_sim_dt

            payload = {
                "timestamp": ev["timestamp"],
                "ap_id": ev["ap_id"],
                "device_id": ev["device_id"],
                "event": ev["event"],
                "rssi": int(ev["rssi"]),
            }

            try:
                resp = await client.post(api_url, json=payload)
                if resp.status_code == 201:
                    sent_count += 1
                    data = resp.json()
                    print(f"[{payload['timestamp']}] Sent -> {payload['ap_id']} | {payload['device_id']} | {payload['event']:<10} (Session #{data.get('session_id')})")
                else:
                    failed_count += 1
                    print(f"Failed to post event ({resp.status_code}): {resp.text}")
            except Exception as e:
                failed_count += 1
                print(f"Network error posting to {api_url}: {e}")

        print(f"\nLive streaming finished. Sent: {sent_count}, Failed: {failed_count}")


if __name__ == "__main__":
    from typing import Optional

    parser = argparse.ArgumentParser(description="Stream simulated events to Wi-Fi Presence API")
    parser.add_argument("--scenario", type=str, choices=["normal_class", "low_attendance", "ap_failure"], default=None)
    parser.add_argument("--duration", type=int, default=60, help="Duration in simulated minutes")
    parser.add_argument("--speed", type=float, default=20.0, help="Speed multiplier (e.g., 20x)")
    parser.add_argument("--url", type=str, default="http://localhost:8000/events", help="API URL")
    args = parser.parse_args()

    asyncio.run(
        forward_live_events(
            scenario_name=args.scenario,
            duration_minutes=args.duration,
            speed_multiplier=args.speed,
            api_url=args.url,
        )
    )
