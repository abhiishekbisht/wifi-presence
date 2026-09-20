"""
Analytics and Export Service.
Computes historical presence intelligence, room utilization, AP activity,
and generates CSV exports of attendance records per PRD Section 4, 14, & 19.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import csv
import io
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import sqlite3

from database.db import get_db_connection
from ml.room_mapping import room_mapping


def get_historical_analytics() -> Dict[str, Any]:
    """
    Computes aggregated historical presence analytics across all rooms and APs:
    1. Daily attendance trend
    2. Room utilization (avg, peak, capacity ratio)
    3. Access point activity distribution
    4. Overall presence confidence trends
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # 1. Daily attendance trends from attendance_estimates
        cursor.execute(
            """
            SELECT date, room_id,
                   AVG(estimated_presence) as avg_presence,
                   AVG(occupancy_pct) as avg_occupancy_pct,
                   AVG(confidence_avg) as avg_confidence,
                   COUNT(*) as record_count
            FROM attendance_estimates
            GROUP BY date, room_id
            ORDER BY date ASC
            """
        )
        daily_rows = cursor.fetchall()
        daily_trends = [dict(r) for r in daily_rows]

        # 2. Room utilization and peak occupancy
        cursor.execute(
            """
            SELECT r.room_id, r.room_name, r.capacity,
                   COALESCE(AVG(ae.occupancy_pct), 0.0) as avg_occupancy_pct,
                   COALESCE(MAX(ae.occupancy_pct), 0.0) as peak_occupancy_pct,
                   COALESCE(AVG(ae.estimated_presence), 0.0) as avg_presence,
                   COALESCE(MAX(ae.estimated_presence), 0) as peak_presence,
                   COALESCE(AVG(ae.confidence_avg), 0.0) as avg_confidence,
                   COUNT(ae.record_id) as total_sessions_recorded
            FROM rooms r
            LEFT JOIN attendance_estimates ae ON r.room_id = ae.room_id
            GROUP BY r.room_id
            """
        )
        room_utilization = [dict(r) for r in cursor.fetchall()]

        # 3. AP activity distribution from events and sessions
        cursor.execute(
            """
            SELECT ap.ap_id, ap.room_id, ap.status,
                   COUNT(e.event_id) as total_events,
                   COUNT(DISTINCT e.device_id) as unique_devices_seen,
                   AVG(e.rssi) as avg_rssi
            FROM access_points ap
            LEFT JOIN events e ON ap.ap_id = e.ap_id
            GROUP BY ap.ap_id
            """
        )
        ap_activity = [dict(r) for r in cursor.fetchall()]

        # 4. Summary KPI Totals
        cursor.execute("SELECT COUNT(*) as total_events_logged FROM events")
        total_events = cursor.fetchone()["total_events_logged"]

        cursor.execute("SELECT COUNT(DISTINCT device_id) as total_devices FROM devices")
        total_unique_devices = cursor.fetchone()["total_devices"]

        cursor.execute("SELECT COUNT(*) as total_sessions FROM sessions")
        total_sessions = cursor.fetchone()["total_sessions"]

        return {
            "summary_kpis": {
                "total_events_logged": total_events,
                "total_unique_devices": total_unique_devices,
                "total_sessions_created": total_sessions,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "daily_trends": daily_trends,
            "room_utilization": room_utilization,
            "ap_activity": ap_activity,
        }
    finally:
        conn.close()


def get_attendance_by_date(date_str: str) -> List[Dict[str, Any]]:
    """Retrieve attendance estimates for a specific date (YYYY-MM-DD)."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT record_id, room_id, date, class_start, class_end,
                   active_devices, estimated_presence, occupancy_pct, confidence_avg
            FROM attendance_estimates
            WHERE date = ?
            ORDER BY class_start ASC
            """,
            (date_str,),
        )
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def export_attendance_csv(date_filter: Optional[str] = None) -> str:
    """
    Generates a CSV string of attendance estimates records.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if date_filter:
            cursor.execute(
                """
                SELECT ae.record_id, ae.room_id, r.room_name, r.capacity, ae.date,
                       ae.class_start, ae.class_end, ae.active_devices,
                       ae.estimated_presence, ae.occupancy_pct, ae.confidence_avg
                FROM attendance_estimates ae
                JOIN rooms r ON ae.room_id = r.room_id
                WHERE ae.date = ?
                ORDER BY ae.class_start ASC
                """,
                (date_filter,),
            )
        else:
            cursor.execute(
                """
                SELECT ae.record_id, ae.room_id, r.room_name, r.capacity, ae.date,
                       ae.class_start, ae.class_end, ae.active_devices,
                       ae.estimated_presence, ae.occupancy_pct, ae.confidence_avg
                FROM attendance_estimates ae
                JOIN rooms r ON ae.room_id = r.room_id
                ORDER BY ae.date DESC, ae.class_start ASC
                """
            )
        rows = [dict(r) for r in cursor.fetchall()]

        output = io.StringIO()
        fieldnames = [
            "record_id",
            "room_id",
            "room_name",
            "capacity",
            "date",
            "class_start",
            "class_end",
            "active_devices",
            "estimated_presence",
            "occupancy_pct",
            "confidence_avg",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

        return output.getvalue()
    finally:
        conn.close()
