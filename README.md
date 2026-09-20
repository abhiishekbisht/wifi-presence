# Wi-Fi Presence Estimation System

A scalable pipeline for estimating classroom attendance from raw Wi-Fi access point session logs using DBSCAN noise filtering and calibrated static room mappings.

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Initialize Database**:
   The SQLite database (`database/wifi_presence.db`) will be automatically initialized when starting the backend, or you can manually initialize it using:
   ```bash
   python database/init_db.py
   ```

## Running the Application

To start the backend server and open the live operations dashboard in one command:
```bash
./run.sh
```
This will launch the FastAPI backend on `http://localhost:8000` and automatically open the Live NOC Dashboard in your default web browser.

## Running the Live Demo (Viva Sequence)

Once the application is running via `./run.sh`, you can trigger a scripted, rehearsable demo sequence that showcases dynamic occupancy changes, AP failure handling, and real-time dashboard updates.

In a new terminal window, run:
```bash
python simulator/demo_script.py
```
This script will:
1. Start with low occupancy in Room 101.
2. Ramp up device entries dynamically.
3. Simulate an AP hardware failure (AP_01 goes offline).
4. Restore the AP and process a batch of exits.

Watch the Live NOC Dashboard during this script to see the animations and metrics update in real time.

## Evaluation Scripts

The project includes two distinct evaluation tracks to validate both pipeline integrity and real-world estimation accuracy.

### Track A: Simulated Stress Test & Pipeline Correctness
Validates throughput, latency, and correctness against known generated simulator targets.
```bash
python tests/evaluate_pipeline.py
```

### Track B: Real Consented Pilot vs Manual Roll Call
Compares the system's estimated occupancy against a real, consented manual roll-call dataset (validates accuracy in a real-world scenario).
```bash
python tests/real_pilot_eval.py
```

## Known Limitations

**1. MAC Randomization Limitations**
Because modern devices (iOS 14+, Android 10+) rotate MAC addresses on new network connections, a student leaving the building and returning may be counted as a new device if the address rotates. This system assumes intra-day stability while connected to the same campus SSID, but long gaps in connectivity may result in slight over-counting.

**2. Multi-Device Ownership**
The system currently treats 1 device = 1 student. Students carrying a laptop, phone, and tablet (all connected to Wi-Fi) will artificially inflate the raw active count. While DBSCAN filters out some transient noise, seated multi-device users are a known source of positive error (over-estimation) that requires future model calibration based on historical device-ratio baselines.

**3. Boundary Bleed (Adjacent Rooms)**
Offices or hallways immediately adjacent to a classroom may pick up strong signals from devices that are not actually in the room. The static room mapping currently assigns APs to a single room without trilateration, meaning a device sitting right outside the door may be mistakenly classified as "present" if their RSSI is stable and strong.
