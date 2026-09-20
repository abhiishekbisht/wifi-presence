"""
Presence Confidence Scoring Engine.
Implements the multi-factor presence confidence formula per PRD Section 13.
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional

# ==============================================================================
# CONFIGURABLE CONSTANTS (PRD Section 13)
# These are exposed as parameters rather than buried magic numbers.
# ==============================================================================
DEFAULT_WEIGHT_DURATION: float = 0.40
DEFAULT_WEIGHT_AP_CONSISTENCY: float = 0.25
DEFAULT_WEIGHT_RSSI_STABILITY: float = 0.20
DEFAULT_WEIGHT_DBSCAN_NOISE: float = 0.15

DEFAULT_CLASS_DURATION_MINUTES: float = 60.0
DEFAULT_PRESENCE_CONFIDENCE_THRESHOLD: float = 0.60
DEFAULT_MIN_PRESENCE_MINUTES: float = 30.0
DEFAULT_MAX_EXPECTED_RSSI_STD: float = 15.0  # RSSI std normalization factor


@dataclass
class ConfidenceScoreResult:
    """Detailed presence confidence calculation result."""
    confidence: float
    is_present: bool
    duration_score: float
    ap_consistency_score: float
    rssi_stability_score: float
    noise_score: float
    reasons: list[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confidence": round(self.confidence, 4),
            "is_present": self.is_present,
            "sub_scores": {
                "duration_score": round(self.duration_score, 4),
                "ap_consistency_score": round(self.ap_consistency_score, 4),
                "rssi_stability_score": round(self.rssi_stability_score, 4),
                "noise_score": round(self.noise_score, 4),
            },
            "reasons": self.reasons,
        }


def calculate_duration_score(duration_minutes: float, class_duration_minutes: float = DEFAULT_CLASS_DURATION_MINUTES) -> float:
    """
    Computes duration score: min(session_duration / class_duration, 1.0).
    """
    if class_duration_minutes <= 0:
        return 0.0
    return min(max(0.0, float(duration_minutes) / float(class_duration_minutes)), 1.0)


def calculate_ap_consistency_score(ap_transition_count: int, room_dwell_fraction: Optional[float] = None) -> float:
    """
    Computes AP consistency score.
    If room_dwell_fraction is provided, uses it directly; otherwise calculates
    a decay based on AP roam/transition count: 1.0 / (1.0 + transitions).
    """
    if room_dwell_fraction is not None:
        return min(max(0.0, float(room_dwell_fraction)), 1.0)
    
    # 0 transitions -> 1.0; 1 transition -> 0.5; 2 transitions -> 0.33, etc.
    return 1.0 / (1.0 + max(0, int(ap_transition_count)))


def calculate_rssi_stability_score(rssi_std: float, max_expected_std: float = DEFAULT_MAX_EXPECTED_RSSI_STD) -> float:
    """
    Computes RSSI stability score: 1.0 - min(rssi_std / max_expected_std, 1.0).
    A seated, stable device has low RSSI jitter (score near 1.0).
    """
    if rssi_std is None or rssi_std < 0:
        return 0.5
    normalized_jitter = min(float(rssi_std) / float(max_expected_std), 1.0)
    return max(0.0, 1.0 - normalized_jitter)


def calculate_presence_confidence(
    session_duration_minutes: float,
    ap_transition_count: int = 0,
    rssi_std: float = 0.0,
    dbscan_noise_flag: int = 0,  # 1 if labeled noise, 0 otherwise
    room_dwell_fraction: Optional[float] = None,
    class_duration_minutes: float = DEFAULT_CLASS_DURATION_MINUTES,
    confidence_threshold: float = DEFAULT_PRESENCE_CONFIDENCE_THRESHOLD,
    min_presence_minutes: float = DEFAULT_MIN_PRESENCE_MINUTES,
    weight_duration: float = DEFAULT_WEIGHT_DURATION,
    weight_ap_consistency: float = DEFAULT_WEIGHT_AP_CONSISTENCY,
    weight_rssi_stability: float = DEFAULT_WEIGHT_RSSI_STABILITY,
    weight_dbscan_noise: float = DEFAULT_WEIGHT_DBSCAN_NOISE,
) -> ConfidenceScoreResult:
    """
    Evaluates session metrics and outputs overall presence confidence score and decision.
    
    Formula:
        confidence = w_d * duration_score + w_ap * ap_consistency_score
                   + w_r * rssi_stability_score + w_n * (1 - dbscan_noise_flag)

    Presence Criterion:
        confidence >= confidence_threshold AND session_duration >= min_presence_minutes
    """
    # 1. Component sub-scores
    s_duration = calculate_duration_score(session_duration_minutes, class_duration_minutes)
    s_ap = calculate_ap_consistency_score(ap_transition_count, room_dwell_fraction)
    s_rssi = calculate_rssi_stability_score(rssi_std)
    s_noise = 0.0 if dbscan_noise_flag == 1 else 1.0

    # 2. Total weighted confidence
    raw_confidence = (
        weight_duration * s_duration
        + weight_ap_consistency * s_ap
        + weight_rssi_stability * s_rssi
        + weight_dbscan_noise * s_noise
    )
    confidence = min(max(0.0, raw_confidence), 1.0)

    # 3. Decision criteria
    reasons = []
    has_sufficient_confidence = confidence >= confidence_threshold
    has_sufficient_duration = session_duration_minutes >= min_presence_minutes

    if not has_sufficient_duration:
        reasons.append(f"Duration {session_duration_minutes:.1f}m < min threshold {min_presence_minutes:.1f}m")
    if not has_sufficient_confidence:
        reasons.append(f"Confidence {confidence:.2f} < threshold {confidence_threshold:.2f}")

    is_present = has_sufficient_confidence and has_sufficient_duration

    if is_present:
        reasons.append("Meets duration and confidence thresholds for verified presence.")

    return ConfidenceScoreResult(
        confidence=confidence,
        is_present=is_present,
        duration_score=s_duration,
        ap_consistency_score=s_ap,
        rssi_stability_score=s_rssi,
        noise_score=s_noise,
        reasons=reasons,
    )
