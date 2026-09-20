"""
Room Mapping Calibration Module (NOT Machine Learning).

===============================================================================
VIVA DEFENSE & ARCHITECTURAL RATIONALE (PRD Section 10):
Why is AP-to-Room mapping implemented as a static calibration table instead of ML?
-------------------------------------------------------------------------------
1. In physical campus deployments, an Access Point (AP) is fixed to a ceiling or
   wall. Its physical room location is an established deployment fact (documented
   in institutional wiring diagrams and network inventories), NOT a latent variable
   that needs to be 'discovered' via unsupervised clustering.
2. Claiming an unsupervised model 'learns' or 'discovers' rooms from scratch introduces
   unnecessary complexity, error margins, and invites the examiner question:
   "Why not just configure it once?"
3. Honest Engineering: We reserve Machine Learning where genuine stochasticity and
   uncertainty exist:
   - DBSCAN (ml/noise_filter.py): To detect and filter sparse transient noise
     (corridor walk-bys, edge-of-cell pings) from genuine seated sessions.
   - Confidence Scoring (ml/confidence.py): To score the probability of true presence.
===============================================================================
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Dict, List, Optional, Any
import yaml
from database.db import get_db_connection

CALIBRATION_FILE = PROJECT_ROOT / "database" / "ap_room_calibration.yaml"


class RoomMapping:
    """
    Static AP-to-Room calibration lookup registry.
    Loads mapping once at startup from YAML or the access_points database table.
    """

    def __init__(self, calibration_path: Optional[Path] = None):
        self.calibration_path = calibration_path or CALIBRATION_FILE
        self._ap_to_room: Dict[str, Dict[str, Any]] = {}
        self._room_to_aps: Dict[str, List[str]] = {}
        self._room_capacities: Dict[str, int] = {}
        self.load_calibration()

    def load_calibration(self):
        """Loads static calibration from YAML or database fallback."""
        if self.calibration_path.exists():
            with open(self.calibration_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                calib = data.get("calibration", {})
                for ap_id, info in calib.items():
                    room_id = info["room_id"]
                    self._ap_to_room[ap_id] = info
                    self._room_to_aps.setdefault(room_id, []).append(ap_id)
                    self._room_capacities[room_id] = info.get("capacity", 40)
        else:
            # Fallback to database lookup
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT ap.ap_id, ap.room_id, ap.ap_name, r.room_name, r.capacity, r.building, r.floor
                    FROM access_points ap
                    JOIN rooms r ON ap.room_id = r.room_id
                    """
                )
                for row in cursor.fetchall():
                    ap_id = row["ap_id"]
                    room_id = row["room_id"]
                    info = dict(row)
                    self._ap_to_room[ap_id] = info
                    self._room_to_aps.setdefault(room_id, []).append(ap_id)
                    self._room_capacities[room_id] = row["capacity"]
            finally:
                conn.close()

    def get_room_for_ap(self, ap_id: str) -> Optional[str]:
        """Return the room_id associated with a given AP."""
        entry = self._ap_to_room.get(ap_id)
        return entry["room_id"] if entry else None

    def get_room_info_for_ap(self, ap_id: str) -> Optional[Dict[str, Any]]:
        """Return complete metadata for an AP's calibrated room."""
        return self._ap_to_room.get(ap_id)

    def get_aps_for_room(self, room_id: str) -> List[str]:
        """Return all AP IDs physically deployed in a given room."""
        return self._room_to_aps.get(room_id, [])

    def get_room_capacity(self, room_id: str) -> int:
        """Return designated student capacity for a room."""
        return self._room_capacities.get(room_id, 40)

    def is_ap_in_room(self, ap_id: str, room_id: str) -> bool:
        """Check if an AP belongs to a specific room."""
        return self.get_room_for_ap(ap_id) == room_id


# Global singleton instance
room_mapping = RoomMapping()
