"""
Live Viva Demo Script.
Provides a rehearsable, fixed sequence of events for the final viva presentation.
Sequence:
1. Low occupancy start in Room 101.
2. Ramp up entries over ~60 seconds.
3. Mid-demo AP failure simulation.
4. Batch exits.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import time
import requests

API_URL = "http://localhost:8000"

def simulate_entry(room_id, ap_id=None):
    try:
        requests.post(f"{API_URL}/demo/simulate-entry", json={"room_id": room_id, "ap_id": ap_id})
        print(f"[+] Simulated entry in {room_id}")
    except Exception as e:
        print(f"Error simulating entry: {e}")

def simulate_exit(room_id, ap_id=None):
    try:
        requests.post(f"{API_URL}/demo/simulate-exit", json={"room_id": room_id, "ap_id": ap_id})
        print(f"[-] Simulated exit in {room_id}")
    except Exception as e:
        print(f"Error simulating exit: {e}")

def toggle_ap(ap_id, status):
    try:
        requests.post(f"{API_URL}/demo/toggle-ap", json={"ap_id": ap_id, "status": status})
        print(f"[!] Toggled AP {ap_id} to {status}")
    except Exception as e:
        print(f"Error toggling AP: {e}")

def run_demo():
    print("=========================================")
    print(" Starting Live Viva Demo Sequence")
    print("=========================================\n")

    print("Phase 1: Initializing Low Occupancy (Room 101)")
    # Add a few initial students
    for _ in range(5):
        simulate_entry("Room 101")
        time.sleep(0.5)

    print("\nPhase 2: Ramping up entries over 30 seconds")
    # Ramp up over 30 seconds to show dynamic updates
    for i in range(15):
        simulate_entry("Room 101")
        simulate_entry("Room 102")
        if i % 3 == 0:
            simulate_entry("Lab 1")
        time.sleep(2)

    print("\nPhase 3: AP Failure Simulation")
    toggle_ap("AP_01", "offline")
    print("Waiting 15 seconds to observe dashboard behavior...")
    time.sleep(15)
    
    print("\nPhase 4: Restoring AP")
    toggle_ap("AP_01", "online")
    time.sleep(5)

    print("\nPhase 5: Batch Exits (Class ending)")
    for _ in range(10):
        simulate_exit("Room 101")
        simulate_exit("Room 102")
        time.sleep(1)

    print("\n=========================================")
    print(" Demo Sequence Complete")
    print("=========================================")

if __name__ == "__main__":
    run_demo()
