"""
Track B Real Pilot Evaluation Script (PRD Section 14).
Compares Wi-Fi session estimation against a real, consented manual roll-call dataset.
Calculates MAE, Precision, Recall, and F1 Score.

VIVA DEFENSE RATIONALE:
- Track A (evaluate_pipeline.py): Simulated stress test (validates latency and pipeline correctness).
- Track B (real_pilot_eval.py): Real pilot evaluation against manual roll call (validates accuracy).
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import csv
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from database.db import get_db_connection
from ml.occupancy import compute_room_occupancy


def evaluate_real_pilot(ground_truth_csv_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Evaluates system estimates against a real pilot manual roll-call CSV.
    """
    csv_file = ground_truth_csv_path or (PROJECT_ROOT / "data" / "pilot_ground_truth.csv")
    print(f"=================================================================")
    print(f" TRACK B EVALUATION: Real Consented Pilot vs Manual Roll Call   ")
    print(f" Source: {csv_file}")
    print(f"=================================================================\n")

    if not csv_file.exists():
        print(f"Error: Pilot ground truth file '{csv_file}' not found.")
        return {}

    pilot_records = []
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pilot_records.append(row)

    print(f"-> Loaded {len(pilot_records)} manual roll-call pilot sessions.\n")

    conn = get_db_connection()
    results = []
    total_abs_error = 0.0
    total_actual = 0
    total_estimated = 0

    # True positives, False positives, False negatives accumulators
    tp_total = 0
    fp_total = 0
    fn_total = 0

    print(f"{'Room ID':<10} | {'Date':<10} | {'Roll Call Target':<17} | {'Active Seen':<12} | {'Estimated Pres':<15} | {'Occ %':<8} | {'Avg Conf':<9} | {'Abs Error':<9}")
    print("-" * 110)

    try:
        for rec in pilot_records:
            room_id = rec["room_id"]
            actual_count = int(rec["actual_present_count"])
            start_dt = datetime.fromisoformat(rec["start_time"].replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(rec["end_time"].replace("Z", "+00:00"))

            occ = compute_room_occupancy(
                room_id,
                conn=conn,
                time_window_start=start_dt,
                time_window_end=end_dt,
                min_presence_minutes=20.0,
            )

            estimated = occ["estimated_presence"]
            active_seen = occ["active_devices"]
            abs_err = abs(actual_count - estimated)
            total_abs_error += abs_err
            total_actual += actual_count
            total_estimated += estimated

            # Classification counts
            tp = min(actual_count, estimated)
            fp = max(0, estimated - actual_count)
            fn = max(0, actual_count - estimated)

            tp_total += tp
            fp_total += fp
            fn_total += fn

            results.append({
                "room_id": room_id,
                "date": rec["date"],
                "actual_count": actual_count,
                "active_seen": active_seen,
                "estimated": estimated,
                "occupancy_pct": occ["occupancy_pct"],
                "confidence_avg": occ["confidence_avg"],
                "abs_error": abs_err,
                "tp": tp,
                "fp": fp,
                "fn": fn,
            })

            print(
                f"{room_id:<10} | {rec['date']:<10} | {actual_count:<17} | "
                f"{active_seen:<12} | {estimated:<15} | {occ['occupancy_pct']:<7.1f}% | "
                f"{occ['confidence_avg']:<9.2f} | {abs_err:<9}"
            )

        mae = total_abs_error / len(pilot_records) if pilot_records else 0.0
        precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) > 0 else 1.0
        recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) > 0 else 1.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        print("-" * 110)
        print(f"\n>> TRACK B PILOT PERFORMANCE METRICS:")
        print(f"   • Mean Absolute Error (MAE) : {mae:.2f} students")
        print(f"   • Precision                 : {precision * 100:.1f}%")
        print(f"   • Recall                    : {recall * 100:.1f}%")
        print(f"   • F1 Score                  : {f1 * 100:.1f}%")
        print(f"\n>> VIVA TAKEAWAY:")
        print(f"   'Simulated ground truth tells us the pipeline works;")
        print(f"    This pilot tells us the occupancy estimate is meaningful.' (PRD Section 14)\n")

        return {
            "mae": mae,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "sessions_evaluated": len(pilot_records),
            "breakdown": results,
        }

    finally:
        conn.close()


if __name__ == "__main__":
    evaluate_real_pilot()
