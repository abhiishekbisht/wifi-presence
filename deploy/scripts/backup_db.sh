#!/bin/bash
# ==============================================================================
# SQLite Database Backup Script for Wi-Fi Presence System
# ==============================================================================

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." &> /dev/null && pwd )"

DB_FILE="${DB_PATH:-$PROJECT_ROOT/database/wifi_presence.db}"
BACKUP_DIR="${BACKUP_DEST:-$PROJECT_ROOT/database/backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/wifi_presence_$TIMESTAMP.db"

mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB_FILE" ]; then
    echo "[!] Error: Database file not found at $DB_FILE"
    exit 1
fi

echo "[+] Starting safe online SQLite backup..."
# Use sqlite3 .backup command for ACID-safe snapshot without locking
sqlite3 "$DB_FILE" ".backup '$BACKUP_FILE'"

# Compress backup
gzip -f "$BACKUP_FILE"
echo "[+] Backup created successfully: ${BACKUP_FILE}.gz"

# Retention policy: keep last 14 days of backups
echo "[+] Cleaning up backups older than 14 days..."
find "$BACKUP_DIR" -name "wifi_presence_*.db.gz" -type f -mtime +14 -delete

echo "[✓] Backup completed."
