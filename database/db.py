"""
Database connection and session utilities for Wi-Fi Presence Estimation System.
"""
from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from backend.config import settings
    DB_PATH = settings.sqlite_db_path
except Exception:
    DB_PATH = BASE_DIR / "database" / "wifi_presence.db"

SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"


def get_db_connection() -> sqlite3.Connection:
    """Return a connection with row factory configured to sqlite3.Row."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

