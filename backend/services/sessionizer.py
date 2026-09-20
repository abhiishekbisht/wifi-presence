"""
Sessionizer Service.
Groups discrete connect/heartbeat/disconnect events per device into cohesive sessions,
computes PRD Section 11 feature metrics, and manages inactivity timeouts.
"""
from datetime import datetime, timezone
import math
import sqlite3
from typing import Dict, List, Optional, Any
from database.db import get_db_connection


class ActiveSession:
    """Represents an ongoing in-memory device session."""

    def __init__(self, session_id: Optional[int], device_id: str, ap_id: str, start_time: datetime):
        self.session_id: Optional[int] = session_id
        self.device_id: str = device_id
        self.current_ap_id: str = ap_id
        self.start_time: datetime = start_time
        self.last_event_time: datetime = start_time
        self.rssi_samples: List[int] = []
        self.connection_count: int = 1
        self.ap_transitions: int = 0
        self.is_closed: bool = False

    def add_event(self, ap_id: str, event_type: str, rssi: int, event_time: datetime):
        self.last_event_time = event_time
        self.connection_count += 1
        self.rssi_samples.append(rssi)

        if ap_id != self.current_ap_id:
            self.ap_transitions += 1
            self.current_ap_id = ap_id

        if event_type == "disconnect":
            self.is_closed = True

    def compute_features(self) -> Dict[str, Any]:
        """Compute PRD Section 11 session features."""
        duration_seconds = max(0.0, (self.last_event_time - self.start_time).total_seconds())
        duration_minutes = round(duration_seconds / 60.0, 2)
        active_minutes = duration_minutes

        if self.rssi_samples:
            avg_rssi = round(sum(self.rssi_samples) / len(self.rssi_samples), 2)
            variance = sum((x - avg_rssi) ** 2 for x in self.rssi_samples) / len(self.rssi_samples)
            rssi_std = round(math.sqrt(variance), 2)
        else:
            avg_rssi = 0.0
            rssi_std = 0.0

        return {
            "duration": duration_minutes,
            "connection_count": self.connection_count,
            "avg_rssi": avg_rssi,
            "rssi_std": rssi_std,
            "active_minutes": active_minutes,
            "ap_transition_count": self.ap_transitions,
            "start_time": self.start_time.isoformat(),
            "end_time": self.last_event_time.isoformat(),
        }


class Sessionizer:
    """Manages active sessions across all devices."""

    def __init__(self, inactivity_timeout_seconds: int = 300):
        self.inactivity_timeout_seconds = inactivity_timeout_seconds
        self.active_sessions: Dict[str, ActiveSession] = {}

    def process_event(self, event_data: Dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> Optional[int]:
        """
        Processes an incoming event, updating or closing sessions.
        Returns the session_id associated with this event.
        """
        device_id = event_data["device_id"]
        ap_id = event_data["ap_id"]
        event_type = event_data["event"]
        rssi = int(event_data["rssi"])
        
        # Parse timestamp
        raw_ts = event_data["timestamp"]
        if isinstance(raw_ts, datetime):
            event_time = raw_ts
        else:
            event_time = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))

        owns_connection = False
        if conn is None:
            conn = get_db_connection()
            owns_connection = True

        try:
            active = self.active_sessions.get(device_id)

            # Check for inactivity timeout on existing session
            if active and (event_time - active.last_event_time).total_seconds() > self.inactivity_timeout_seconds:
                self._persist_session(active, conn, is_final=True)
                del self.active_sessions[device_id]
                active = None

            if active is None:
                # Create a new session on connect or first sighting
                active = ActiveSession(
                    session_id=None,
                    device_id=device_id,
                    ap_id=ap_id,
                    start_time=event_time,
                )
                active.rssi_samples.append(rssi)
                self.active_sessions[device_id] = active

                # Ensure device exists in devices table to satisfy foreign key constraint
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO devices (device_id, first_seen, last_seen)
                    VALUES (?, ?, ?)
                    ON CONFLICT(device_id) DO UPDATE SET
                        last_seen = excluded.last_seen
                    """,
                    (device_id, event_time.isoformat(), event_time.isoformat()),
                )

                # Insert initial session row in SQLite
                cursor.execute(
                    """
                    INSERT INTO sessions (
                        device_id, ap_id, start_time, end_time, duration,
                        connection_count, avg_rssi, rssi_std, active_minutes,
                        ap_transition_count, confidence, dbscan_label
                    ) VALUES (?, ?, ?, ?, 0.0, 1, ?, 0.0, 0.0, 0, 0.0, 'unassigned')
                    """,
                    (device_id, ap_id, event_time.isoformat(), event_time.isoformat(), rssi),
                )
                active.session_id = cursor.lastrowid
                conn.commit()


            else:
                # Update existing active session
                active.add_event(ap_id, event_type, rssi, event_time)
                self._persist_session(active, conn, is_final=active.is_closed)

                if active.is_closed:
                    del self.active_sessions[device_id]

            return active.session_id

        finally:
            if owns_connection:
                conn.close()

    def _persist_session(self, session: ActiveSession, conn: sqlite3.Connection, is_final: bool = False):
        """Update session metrics in SQLite."""
        features = session.compute_features()
        cursor = conn.cursor()

        if session.session_id:
            cursor.execute(
                """
                UPDATE sessions SET
                    ap_id = ?,
                    end_time = ?,
                    duration = ?,
                    connection_count = ?,
                    avg_rssi = ?,
                    rssi_std = ?,
                    active_minutes = ?,
                    ap_transition_count = ?
                WHERE session_id = ?
                """,
                (
                    session.current_ap_id,
                    features["end_time"],
                    features["duration"],
                    features["connection_count"],
                    features["avg_rssi"],
                    features["rssi_std"],
                    features["active_minutes"],
                    features["ap_transition_count"],
                    session.session_id,
                ),
            )
            conn.commit()

    def check_inactivity_timeouts(self, current_time: Optional[datetime] = None) -> List[int]:
        """Close any sessions that have exceeded the inactivity timeout."""
        now = current_time or datetime.now(timezone.utc)
        timed_out_devs = []

        conn = get_db_connection()
        try:
            for dev_id, session in list(self.active_sessions.items()):
                if (now - session.last_event_time).total_seconds() > self.inactivity_timeout_seconds:
                    self._persist_session(session, conn, is_final=True)
                    timed_out_devs.append(session.session_id)
                    del self.active_sessions[dev_id]
            return timed_out_devs
        finally:
            conn.close()


sessionizer = Sessionizer()
