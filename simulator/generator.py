"""
Wi-Fi Event Simulator.
Implements batch and asynchronous live event generation per PRD Section 5 & Section 9.
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import asyncio
import csv
import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Dict, List, Optional, Any
import yaml

CONFIG_PATH = PROJECT_ROOT / "simulator" / "config.yaml"


def generate_salted_device_id(raw_mac: str, ssid: str, salt: str) -> str:
    """
    Generate an anonymized, irreversible device_id from (MAC, SSID, Salt).
    Preserves per-SSID stability as documented in PRD Section 5 & 9.
    """
    payload = f"{salt}:{ssid}:{raw_mac}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:16]
    return f"dev_{digest}"


class WiFiEventSimulator:
    """
    Simulates realistic Wi-Fi access point events (connect, heartbeat, disconnect)
    for classroom presence and occupancy estimation.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_PATH
        self.config = self._load_config()
        self.rooms = self.config["topology"]["rooms"]
        self.sim_cfg = self.config["simulation"]
        self.behavior_cfg = self.config["behavior"]
        self.rssi_profiles = self.config["rssi_profiles"]
        self.devices = self._initialize_device_pool()

    def _load_config(self) -> Dict[str, Any]:
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _initialize_device_pool(self) -> List[Dict[str, str]]:
        pool = []
        salt = self.sim_cfg.get("hash_salt", "wifi-presence-salt-2026")
        ssid = self.sim_cfg.get("campus_ssid", "CAMPUS_STUDENT_WIFI")
        total_devices = self.sim_cfg.get("total_device_pool", 60)

        for i in range(total_devices):
            mac = f"02:00:00:{random.randint(0, 255):02x}:{random.randint(0, 255):02x}:{i:02x}"
            device_id = generate_salted_device_id(mac, ssid, salt)
            pool.append({"device_id": device_id, "mac": mac})
        return pool

    def _sample_rssi(self, profile_name: str) -> int:
        prof = self.rssi_profiles.get(profile_name, self.rssi_profiles["seated"])
        val = int(random.gauss(prof["mean"], prof["std"]))
        return max(prof["min"], min(prof["max"], val))

    def generate_event_plan(
        self,
        start_time: Optional[datetime] = None,
        duration_minutes: Optional[int] = None,
        ap_outages: Optional[List[Dict[str, Any]]] = None,
        attendance_targets: Optional[Dict[str, int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Plans and orders all discrete events across the simulation window.
        Returns a sorted list of event dictionaries.
        """
        start = start_time or datetime.now(timezone.utc)
        duration_mins = duration_minutes or self.sim_cfg.get("class_duration_minutes", 60)
        end_time = start + timedelta(minutes=duration_mins)
        hb_interval = self.sim_cfg.get("heartbeat_interval_seconds", 30)

        events: List[Dict[str, Any]] = []
        available_devices = list(self.devices)
        random.shuffle(available_devices)

        dev_index = 0

        # Plan for each room
        for room in self.rooms:
            room_id = room["id"]
            ap_ids = room["aps"]
            primary_ap = ap_ids[0]
            capacity = room["capacity"]

            # Target attendance for this room
            if attendance_targets and room_id in attendance_targets:
                target_count = min(capacity, attendance_targets[room_id])
            else:
                target_count = min(capacity, int(capacity * random.uniform(0.70, 0.88)))

            room_devices = available_devices[dev_index : dev_index + target_count]
            dev_index += target_count

            for dev in room_devices:
                device_id = dev["device_id"]
                current_ap = primary_ap

                # Behavior archetype
                is_walkby = random.random() < self.behavior_cfg.get("walkby_probability", 0.15)
                is_transitioning = random.random() < self.behavior_cfg.get("transition_probability", 0.10)
                is_late = random.random() < self.behavior_cfg.get("late_arrival_probability", 0.20)
                is_early_leave = random.random() < self.behavior_cfg.get("early_departure_probability", 0.15)

                if is_walkby:
                    # Edge case 1: Hallway walk-by transient (5-15 seconds)
                    walk_start = start + timedelta(seconds=random.randint(60, duration_mins * 60 - 60))
                    walk_dur = random.randint(5, 15)
                    walk_end = walk_start + timedelta(seconds=walk_dur)

                    events.append({
                        "timestamp": walk_start.isoformat(),
                        "ap_id": current_ap,
                        "device_id": device_id,
                        "event": "connect",
                        "rssi": self._sample_rssi("transient"),
                        "_dt": walk_start,
                    })
                    events.append({
                        "timestamp": walk_end.isoformat(),
                        "ap_id": current_ap,
                        "device_id": device_id,
                        "event": "disconnect",
                        "rssi": self._sample_rssi("transient"),
                        "_dt": walk_end,
                    })
                    continue

                # Seated regular or roaming device
                dev_start = start + timedelta(minutes=random.randint(5, 15)) if is_late else start + timedelta(seconds=random.randint(0, 120))
                dev_end = end_time - timedelta(minutes=random.randint(10, 20)) if is_early_leave else end_time - timedelta(seconds=random.randint(0, 60))

                if dev_end <= dev_start:
                    dev_end = dev_start + timedelta(minutes=10)

                # Connect event
                events.append({
                    "timestamp": dev_start.isoformat(),
                    "ap_id": current_ap,
                    "device_id": device_id,
                    "event": "connect",
                    "rssi": self._sample_rssi("seated"),
                    "_dt": dev_start,
                })

                # Transition timestamp if applicable
                trans_time = None
                target_trans_ap = None
                if is_transitioning and len(self.rooms) > 1:
                    # Pick an adjacent room AP
                    other_aps = [r["aps"][0] for r in self.rooms if r["aps"][0] != current_ap]
                    if other_aps:
                        target_trans_ap = random.choice(other_aps)
                        trans_offset = (dev_end - dev_start).total_seconds() * random.uniform(0.3, 0.7)
                        trans_time = dev_start + timedelta(seconds=int(trans_offset))

                # Generate heartbeats
                curr = dev_start + timedelta(seconds=hb_interval)
                transition_occurred = False

                while curr < dev_end:
                    # Check if transitioning AP
                    if trans_time and curr >= trans_time and not transition_occurred:
                        # Edge case 2: Roam/transition between APs mid-class
                        events.append({
                            "timestamp": curr.isoformat(),
                            "ap_id": current_ap,
                            "device_id": device_id,
                            "event": "disconnect",
                            "rssi": self._sample_rssi("moving"),
                            "_dt": curr,
                        })
                        current_ap = target_trans_ap
                        curr += timedelta(seconds=2)
                        events.append({
                            "timestamp": curr.isoformat(),
                            "ap_id": current_ap,
                            "device_id": device_id,
                            "event": "connect",
                            "rssi": self._sample_rssi("seated"),
                            "_dt": curr,
                        })
                        transition_occurred = True

                    events.append({
                        "timestamp": curr.isoformat(),
                        "ap_id": current_ap,
                        "device_id": device_id,
                        "event": "heartbeat",
                        "rssi": self._sample_rssi("seated"),
                        "_dt": curr,
                    })
                    curr += timedelta(seconds=hb_interval + random.randint(-3, 3))

                # Disconnect event
                events.append({
                    "timestamp": dev_end.isoformat(),
                    "ap_id": current_ap,
                    "device_id": device_id,
                    "event": "disconnect",
                    "rssi": self._sample_rssi("seated"),
                    "_dt": dev_end,
                })

        # Filter out events during planned AP outages (Edge case 3)
        if ap_outages:
            filtered_events = []
            for ev in events:
                suppressed = False
                for outage in ap_outages:
                    if ev["ap_id"] == outage["ap_id"]:
                        o_start = outage["start"]
                        o_end = outage["end"]
                        if o_start <= ev["_dt"] <= o_end:
                            suppressed = True
                            break
                if not suppressed:
                    filtered_events.append(ev)
            events = filtered_events

        # Sort chronologically
        events.sort(key=lambda x: x["_dt"])

        # Strip internal temporary datetime object before returning
        clean_events = []
        for e in events:
            ev_clean = {k: v for k, v in e.items() if not k.startswith("_")}
            ev_clean["_dt"] = e["_dt"]  # keep for live async timing
            clean_events.append(ev_clean)

        return clean_events

    def generate_batch_events(
        self,
        output_csv_path: Optional[Path] = None,
        duration_minutes: Optional[int] = None,
        attendance_targets: Optional[Dict[str, int]] = None,
        ap_outages: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Batch mode: Generates events and writes them to a CSV file.
        """
        start_time = datetime.now(timezone.utc)
        events = self.generate_event_plan(
            start_time=start_time,
            duration_minutes=duration_minutes,
            ap_outages=ap_outages,
            attendance_targets=attendance_targets,
        )

        output_path = output_csv_path or (PROJECT_ROOT / "data" / "sample_logs.csv")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = ["timestamp", "ap_id", "device_id", "event", "rssi"]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for ev in events:
                row = {k: ev[k] for k in fieldnames}
                writer.writerow(row)

        # Return list of pure schema dicts without _dt
        return [{k: ev[k] for k in fieldnames} for ev in events]

    async def generate_live_events(
        self,
        duration_minutes: Optional[int] = None,
        speed_multiplier: Optional[float] = None,
        attendance_targets: Optional[Dict[str, int]] = None,
        ap_outages: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Live mode: Asynchronously yields events in real time with speed_multiplier pacing.
        E.g. speed_multiplier=20 runs 60 simulated minutes in 3 real minutes.
        """
        speed = speed_multiplier or self.sim_cfg.get("default_speed_multiplier", 15.0)
        start_time = datetime.now(timezone.utc)
        events = self.generate_event_plan(
            start_time=start_time,
            duration_minutes=duration_minutes,
            ap_outages=ap_outages,
            attendance_targets=attendance_targets,
        )

        if not events:
            return

        first_sim_dt = events[0]["_dt"]
        last_sim_dt = first_sim_dt

        for ev in events:
            curr_sim_dt = ev["_dt"]
            delta_sim_seconds = (curr_sim_dt - last_sim_dt).total_seconds()
            if delta_sim_seconds > 0:
                sleep_real_seconds = delta_sim_seconds / speed
                await asyncio.sleep(sleep_real_seconds)
            last_sim_dt = curr_sim_dt

            # Yield clean event matching PRD schema
            yield {
                "timestamp": ev["timestamp"],
                "ap_id": ev["ap_id"],
                "device_id": ev["device_id"],
                "event": ev["event"],
                "rssi": ev["rssi"],
            }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wi-Fi Event Simulator CLI")
    parser.add_argument("--mode", choices=["batch", "live"], default="batch")
    parser.add_argument("--output", type=str, default="data/sample_logs.csv")
    parser.add_argument("--duration", type=int, default=60, help="Class duration in minutes")
    parser.add_argument("--speed", type=float, default=20.0, help="Speed multiplier for live mode")
    args = parser.parse_args()

    sim = WiFiEventSimulator()

    if args.mode == "batch":
        out_path = PROJECT_ROOT / args.output
        events = sim.generate_batch_events(output_csv_path=out_path, duration_minutes=args.duration)
        print(f"Generated {len(events)} batch events written to {out_path}")
    elif args.mode == "live":
        async def run_live():
            print(f"Starting live event stream (speed: {args.speed}x, duration: {args.duration}m)...")
            count = 0
            async for ev in sim.generate_live_events(duration_minutes=args.duration, speed_multiplier=args.speed):
                count += 1
                print(f"[{ev['timestamp']}] {ev['ap_id']} | {ev['device_id']} | {ev['event']:<10} | RSSI: {ev['rssi']}")
            print(f"Live stream completed. Emitted {count} events.")

        asyncio.run(run_live())
