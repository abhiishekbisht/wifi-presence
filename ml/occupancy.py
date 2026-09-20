"""
Room Occupancy Estimation Engine.
Integrates calibration table lookup, DBSCAN noise filtering, and presence confidence scoring
to compute room occupancy metrics and persist attendance estimates per PRD Section 13 & 18.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import sqlite3

from database.db import get_db_connection
from ml.room_mapping import room_mapping
from ml.noise_filter import filter_sessions_dbscan
from ml.confidence import calculate_presence_confidence, DEFAULT_PRESENCE_CONFIDENCE_THRESHOLD, DEFAULT_MIN_PRESENCE_MINUTES


def get_room_sessions(
    room_id: str,
    conn: Optional[sqlite3.Connection] = None,
    time_window_start: Optional[datetime] = None,
    time_window_end: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve all sessions associated with APs in a specific room.
    """
    aps = room_mapping.get_aps_for_room(room_id)
    if not aps:
        return []

    owns_conn = False
    if conn is None:
        conn = get_db_connection()
        owns_conn = True

    try:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in aps)

        if time_window_start and time_window_end:
            query = f"""
                SELECT * FROM sessions
                WHERE ap_id IN ({placeholders})
                AND start_time <= ?
                AND (end_time >= ? OR end_time IS NULL)
            """
            params = list(aps) + [time_window_end.isoformat(), time_window_start.isoformat()]
        else:
            query = f"""
                SELECT * FROM sessions
                WHERE ap_id IN ({placeholders})
                ORDER BY start_time DESC
            """
            params = list(aps)

        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]
    finally:
        if owns_conn:
            conn.close()


def compute_room_occupancy(
    room_id: str,
    conn: Optional[sqlite3.Connection] = None,
    time_window_start: Optional[datetime] = None,
    time_window_end: Optional[datetime] = None,
    persist_estimate: bool = False,
    class_duration_minutes: float = 60.0,
    min_presence_minutes: float = DEFAULT_MIN_PRESENCE_MINUTES,
    confidence_threshold: float = DEFAULT_PRESENCE_CONFIDENCE_THRESHOLD,
) -> Dict[str, Any]:
    """
    Computes live occupancy, device presence count, and average confidence for a room.
    """
    owns_conn = False
    if conn is None:
        conn = get_db_connection()
        owns_conn = True

    try:
        raw_sessions = get_room_sessions(
            room_id,
            conn=conn,
            time_window_start=time_window_start,
            time_window_end=time_window_end,
        )

        capacity = room_mapping.get_room_capacity(room_id)
        room_info = room_mapping._ap_to_room.get(
            room_mapping.get_aps_for_room(room_id)[0] if room_mapping.get_aps_for_room(room_id) else "", {}
        )
        room_name = room_info.get("room_name", room_id)

        if not raw_sessions:
            return {
                "room_id": room_id,
                "room_name": room_name,
                "capacity": capacity,
                "active_devices": 0,
                "estimated_presence": 0,
                "occupancy_pct": 0.0,
                "confidence_avg": 0.0,
                "present_device_ids": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # 1. Apply DBSCAN noise filtering to session feature vectors
        filtered_sessions = filter_sessions_dbscan(raw_sessions)

        # 2. Score presence confidence per session
        present_device_ids = []
        confidences = []

        # Deduplicate per device (keep most confident session if multiple)
        device_best_session: Dict[str, Dict[str, Any]] = {}

        for s in filtered_sessions:
            dev_id = s["device_id"]
            dur = float(s.get("duration", 0.0))
            rssi_std = float(s.get("rssi_std", 0.0))
            transitions = int(s.get("ap_transition_count", 0))
            noise_flag = int(s.get("dbscan_noise_flag", 0))

            score_res = calculate_presence_confidence(
                session_duration_minutes=dur,
                ap_transition_count=transitions,
                rssi_std=rssi_std,
                dbscan_noise_flag=noise_flag,
                class_duration_minutes=class_duration_minutes,
                confidence_threshold=confidence_threshold,
                min_presence_minutes=min_presence_minutes,
            )

            s["confidence"] = score_res.confidence
            s["is_present"] = score_res.is_present

            if dev_id not in device_best_session or score_res.confidence > device_best_session[dev_id]["confidence"]:
                device_best_session[dev_id] = s

        # Tally unique devices
        active_devices = len(device_best_session)
        present_sessions = [s for s in device_best_session.values() if s.get("is_present", False)]
        estimated_presence = len(present_sessions)
        present_device_ids = [s["device_id"] for s in present_sessions]

        if present_sessions:
            confidence_avg = round(sum(s["confidence"] for s in present_sessions) / len(present_sessions), 4)
        else:
            confidence_avg = 0.0

        occupancy_pct = round(min(100.0, (estimated_presence / capacity) * 100.0), 1) if capacity > 0 else 0.0
        now_ts = datetime.now(timezone.utc).isoformat()

        # 3. Optionally persist attendance estimate snapshot
        if persist_estimate:
            cursor = conn.cursor()
            w_start = time_window_start.isoformat() if time_window_start else now_ts
            w_end = time_window_end.isoformat() if time_window_end else now_ts
            today_date = (time_window_start or datetime.now(timezone.utc)).strftime("%Y-%m-%d")

            cursor.execute(
                """
                INSERT INTO attendance_estimates (
                    room_id, date, class_start, class_end,
                    active_devices, estimated_presence, occupancy_pct, confidence_avg
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    room_id,
                    today_date,
                    w_start,
                    w_end,
                    active_devices,
                    estimated_presence,
                    occupancy_pct,
                    confidence_avg,
                ),
            )
            conn.commit()

        return {
            "room_id": room_id,
            "room_name": room_name,
            "capacity": capacity,
            "active_devices": active_devices,
            "estimated_presence": estimated_presence,
            "occupancy_pct": occupancy_pct,
            "confidence_avg": confidence_avg,
            "present_device_ids": present_device_ids,
            "timestamp": now_ts,
        }

    finally:
        if owns_conn:
            conn.close()


def get_all_rooms_occupancy() -> List[Dict[str, Any]]:
    """Returns occupancy metrics for all configured rooms."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT room_id FROM rooms")
        rooms = [r["room_id"] for r in cursor.fetchall()]
        return [compute_room_occupancy(r_id, conn=conn) for r_id in rooms]
    finally:
        conn.close()
