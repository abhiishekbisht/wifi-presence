"""
DBSCAN Noise Filtering Module.
Applies density-based spatial clustering of applications with noise (DBSCAN)
to session feature vectors within a room per PRD Section 12.

VIVA DEFENSE RATIONALE:
- DBSCAN is applied to feature vectors (duration, avg_rssi, rssi_std, ap_transition_count), NOT AP coordinates.
- It separates dense clusters of genuine, seated presence from sparse transient outliers (walk-bys)
  without requiring a preset cluster count (K).
- Sparse points are explicitly labeled as 'noise' (flag = 1), feeding into the confidence score.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import List, Dict, Any, Tuple
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler


def filter_sessions_dbscan(
    sessions: List[Dict[str, Any]],
    eps: float = 0.85,
    min_samples: int = 3,
) -> List[Dict[str, Any]]:
    """
    Classifies a list of sessions within a room into 'core', 'border', or 'noise'.
    
    Features used:
    1. duration (minutes)
    2. avg_rssi (dBm)
    3. rssi_std (dBm jitter)
    4. ap_transition_count (roam count)
    
    Returns the enriched session dictionaries with:
    - dbscan_label ('core', 'border', 'noise')
    - dbscan_noise_flag (1 if noise else 0)
    """
    if not sessions:
        return []

    # If too few sessions for clustering, apply baseline heuristic fallback
    if len(sessions) < min_samples:
        enriched = []
        for s in sessions:
            s_copy = dict(s)
            dur = s_copy.get("duration", 0.0)
            # Transient walk-by heuristic if duration < 2 minutes or jitter > 10
            if dur < 2.0 or s_copy.get("rssi_std", 0.0) > 10.0:
                s_copy["dbscan_label"] = "noise"
                s_copy["dbscan_noise_flag"] = 1
            else:
                s_copy["dbscan_label"] = "core"
                s_copy["dbscan_noise_flag"] = 0
            enriched.append(s_copy)
        return enriched

    # 1. Build feature matrix
    feature_matrix = []
    for s in sessions:
        dur = float(s.get("duration", 0.0))
        avg_rssi = float(s.get("avg_rssi", -50.0))
        rssi_std = float(s.get("rssi_std", 0.0))
        transitions = float(s.get("ap_transition_count", 0))
        feature_matrix.append([dur, avg_rssi, rssi_std, transitions])

    X = np.array(feature_matrix, dtype=float)

    # 2. Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 3. Fit DBSCAN
    db = DBSCAN(eps=eps, min_samples=min_samples).fit(X_scaled)
    labels = db.labels_
    core_sample_indices = set(db.core_sample_indices_)

    # 4. Assign labels
    enriched_sessions = []
    for idx, s in enumerate(sessions):
        s_copy = dict(s)
        cluster_id = labels[idx]

        if cluster_id == -1:
            # Noise outlier (e.g. transient 5-15s walk-by or extreme jitter)
            s_copy["dbscan_label"] = "noise"
            s_copy["dbscan_noise_flag"] = 1
        elif idx in core_sample_indices:
            s_copy["dbscan_label"] = "core"
            s_copy["dbscan_noise_flag"] = 0
        else:
            s_copy["dbscan_label"] = "border"
            s_copy["dbscan_noise_flag"] = 0

        enriched_sessions.append(s_copy)

    return enriched_sessions
