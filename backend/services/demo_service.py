"""
Demo Service.
Provides live interactive simulation actions (simulate entry, exit, AP failure, and scenario runner)
to power the dashboard's quick-control panel.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import asyncio
import random
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from database.db import get_db_connection
from backend.services.event_service import ingest_event
from backend.websocket.manager import ws_manager
from ml.room_mapping import room_mapping
from simulator.generator import WiFiEventSimulator, generate_salted_device_id
from simulator.scenarios import get_scenario_plan

# Keep reference to ongoing scenario task to prevent garbage collection
_current_scenario_task: Optional[asyncio.Task] = None


async def simulate_device_entry(room_id: str = "Room 101", ap_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Simulates a student entering a room with their mobile device.
    Emits connect and initial heartbeat events.
    """
    if not ap_id:
        aps = room_mapping.get_aps_for_room(room_id)
        ap_id = aps[0] if aps else "AP_01"

    mac = f"02:00:00:{random.randint(0, 255):02x}:{random.randint(0, 255):02x}:{random.randint(0, 255):02x}"
    dev_id = generate_salted_device_id(mac, "CAMPUS_STUDENT_WIFI", "wifi-presence-salt-2026")
    now_iso = datetime.now(timezone.utc).isoformat()
    rssi = random.randint(-55, -42)

    # 1. Connect
    ev_connect = {
        "timestamp": now_iso,
        "ap_id": ap_id,
        "device_id": dev_id,
        "event": "connect",
        "rssi": rssi,
    }
    res = await ingest_event(ev_connect)

    return {
        "action": "simulate_entry",
        "device_id": dev_id,
        "room_id": room_id,
        "ap_id": ap_id,
        "event_result": res,
    }


async def simulate_device_exit(room_id: str = "Room 101", ap_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Simulates a device departing the room by emitting a disconnect event.
    """
    if not ap_id:
        aps = room_mapping.get_aps_for_room(room_id)
        ap_id = aps[0] if aps else "AP_01"

    # Find an active session in this AP from SQLite
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT device_id FROM sessions
            WHERE ap_id = ?
            ORDER BY start_time DESC LIMIT 10
            """,
            (ap_id,),
        )
        rows = cursor.fetchall()
        if not rows:
            return {"action": "simulate_exit", "status": "no_active_devices", "room_id": room_id}

        target_dev = random.choice(rows)["device_id"]
        now_iso = datetime.now(timezone.utc).isoformat()
        rssi = random.randint(-75, -65)

        ev_disconnect = {
            "timestamp": now_iso,
            "ap_id": ap_id,
            "device_id": target_dev,
            "event": "disconnect",
            "rssi": rssi,
        }
        res = await ingest_event(ev_disconnect)

        return {
            "action": "simulate_exit",
            "device_id": target_dev,
            "room_id": room_id,
            "ap_id": ap_id,
            "event_result": res,
        }
    finally:
        conn.close()


async def toggle_ap_status(ap_id: str, new_status: Optional[str] = None) -> Dict[str, Any]:
    """
    Toggles an Access Point between 'online' and 'offline' (simulating hardware / PoE failure).
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status, room_id FROM access_points WHERE ap_id = ?", (ap_id,))
        row = cursor.fetchone()
        if not row:
            return {"status": "error", "message": f"AP {ap_id} not found"}

        current_status = row["status"]
        if new_status:
            status_to_set = new_status
        else:
            status_to_set = "offline" if current_status == "online" else "online"

        cursor.execute("UPDATE access_points SET status = ? WHERE ap_id = ?", (status_to_set, ap_id))
        conn.commit()

        # Broadcast AP status change over WebSocket
        payload = {
            "type": "ap_status_update",
            "ap_id": ap_id,
            "room_id": row["room_id"],
            "status": status_to_set,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await ws_manager.broadcast(payload)

        return {
            "ap_id": ap_id,
            "room_id": row["room_id"],
            "previous_status": current_status,
            "current_status": status_to_set,
        }
    finally:
        conn.close()


async def run_scenario_stream(scenario_name: str = "normal_class", speed_multiplier: float = 30.0):
    """
    Runs a named simulation scenario in the background, feeding events into the ingestion pipeline.
    """
    start_time = datetime.now(timezone.utc)
    events = get_scenario_plan(scenario_name, start_time=start_time)

    if not events:
        return

    first_sim_dt = events[0]["_dt"]
    last_sim_dt = first_sim_dt

    for ev in events:
        curr_sim_dt = ev["_dt"]
        delta_sim_seconds = (curr_sim_dt - last_sim_dt).total_seconds()
        if delta_sim_seconds > 0:
            sleep_real_seconds = delta_sim_seconds / speed_multiplier
            await asyncio.sleep(sleep_real_seconds)
        last_sim_dt = curr_sim_dt

        clean_ev = {
            "timestamp": ev["timestamp"],
            "ap_id": ev["ap_id"],
            "device_id": ev["device_id"],
            "event": ev["event"],
            "rssi": int(ev["rssi"]),
        }
        await ingest_event(clean_ev)


def launch_scenario_background(scenario_name: str = "normal_class", speed_multiplier: float = 30.0):
    """Launches scenario stream task in the current running event loop."""
    global _current_scenario_task
    if _current_scenario_task and not _current_scenario_task.done():
        _current_scenario_task.cancel()

    _current_scenario_task = asyncio.create_task(
        run_scenario_stream(scenario_name=scenario_name, speed_multiplier=speed_multiplier)
    )
    return _current_scenario_task
