import sys
from pathlib import Path

# Ensure root directory is on sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import sqlite3
from database.db import DB_PATH, SCHEMA_PATH



def init_db(seed_sample_data: bool = True):
    """Initialize database and seed baseline rooms/APs."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.executescript(schema_sql)

    if seed_sample_data:
        # Seed baseline rooms per PRD Section 10
        rooms = [
            ("Room 101", "Room 101", 40, "Academic Block A", "1st Floor"),
            ("Room 102", "Room 102", 35, "Academic Block A", "1st Floor"),
            ("Lab 1", "Computer Lab 1", 25, "Science Block", "Ground Floor"),
        ]
        cursor.executemany(
            """
            INSERT OR IGNORE INTO rooms (room_id, room_name, capacity, building, floor)
            VALUES (?, ?, ?, ?, ?)
            """,
            rooms,
        )

        # Seed baseline access points mapped to rooms (Calibration Table)
        access_points = [
            ("AP_01", "Room 101", "AP-Room101-Ceiling", "online"),
            ("AP_02", "Room 102", "AP-Room102-Ceiling", "online"),
            ("AP_03", "Lab 1", "AP-Lab1-Corner", "online"),
        ]
        cursor.executemany(
            """
            INSERT OR IGNORE INTO access_points (ap_id, room_id, ap_name, status)
            VALUES (?, ?, ?, ?)
            """,
            access_points,
        )

    conn.commit()
    conn.close()
    print(f"Database initialized successfully at {DB_PATH}")


if __name__ == "__main__":
    init_db()
