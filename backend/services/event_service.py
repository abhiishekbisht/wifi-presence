"""
Event Ingestion Service.
Coordinates database persistence for events, updates device registry,
invokes sessionizer, recomputes live occupancy, and broadcasts real-time payloads to WebSocket clients.
"""
from datetime import datetime
from typing import Dict, Any, Optional
import sqlite3

from database.db import get_db_connection
from backend.websocket.manager import ws_manager
from backend.services.sessionizer import sessionizer
from ml.room_mapping import room_mapping
from ml.occupancy import compute_room_occupancy


async def ingest_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ingest a single Wi-Fi event:
    1. Persist to `events` table
    2. Upsert device in `devices` table
    3. Update active session and features in `sessions` table
    4. Compute updated live room occupancy
    5. Broadcast event and occupancy updates to WebSocket subscribers
    """
    conn = get_db_connection()
    try:
        timestamp_str = event_data["timestamp"]
        if isinstance(timestamp_str, datetime):
            timestamp_str = timestamp_str.isoformat()

        cursor = conn.cursor()

        # 1. Upsert device
        cursor.execute(
            """
            INSERT INTO devices (device_id, first_seen, last_seen)
            VALUES (?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                last_seen = excluded.last_seen
            """,
            (event_data["device_id"], timestamp_str, timestamp_str),
        )

        # 2. Insert event
        cursor.execute(
            """
            INSERT INTO events (timestamp, device_id, ap_id, event_type, rssi)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                timestamp_str,
                event_data["device_id"],
                event_data["ap_id"],
                event_data["event"],
                event_data["rssi"],
            ),
        )
        event_id = cursor.lastrowid
        conn.commit()

        # 3. Process session
        session_id = sessionizer.process_event(event_data, conn=conn)

        # 4. Compute updated occupancy for the room this AP belongs to
        room_id = room_mapping.get_room_for_ap(event_data["ap_id"])
        room_occupancy = None
        if room_id:
            room_occupancy = compute_room_occupancy(room_id, conn=conn)

        # Build payload for WebSocket broadcast
        broadcast_payload = {
            "type": "event",
            "event_id": event_id,
            "session_id": session_id,
            "timestamp": timestamp_str,
            "ap_id": event_data["ap_id"],
            "device_id": event_data["device_id"],
            "event": event_data["event"],
            "rssi": event_data["rssi"],
            "room_id": room_id,
            "room_occupancy": room_occupancy,
        }

        # 5. Broadcast via WebSocket
        await ws_manager.broadcast(broadcast_payload)

        return {
            "status": "success",
            "event_id": event_id,
            "session_id": session_id,
            "device_id": event_data["device_id"],
            "room_id": room_id,
            "room_occupancy": room_occupancy,
        }

    finally:
        conn.close()
