# Wi-Fi Classroom Presence Estimation

A real-time system that estimates classroom occupancy and device-level presence from Wi-Fi Access Point (AP) session events, with calibrated room mapping, DBSCAN noise filtering, and confidence-scored occupancy analytics.

---

## Project Structure

```
wifi-presence/
├── backend/
│   ├── main.py             # FastAPI entry point & lifespan handler
│   ├── config.py           # Pydantic environment configuration
│   ├── api/                # REST API routers and endpoints
│   ├── models/             # Pydantic schemas and data models
│   ├── services/           # Sessionization and business logic services
│   └── websocket/          # WebSocket managers and live stream handlers
├── ml/                     # ML modules (DBSCAN noise filtering, calibration, confidence scoring)
├── simulator/              # Schema-faithful Wi-Fi event generator and demo scenarios
├── database/
│   ├── schema.sql          # Core SQLite / relational schema
│   ├── db.py               # SQLite connection helper
│   ├── init_db.py          # Database initialization & seeding script
│   └── wifi_presence.db    # SQLite database file
├── dashboard/              # Self-contained dark NOC-style HTML/JS dashboard
├── data/                   # Batch event logs and evaluation datasets
├── tests/                  # Pytest unit, integration, and evaluation suites
├── requirements.txt        # Pinned Python package dependencies
├── .env.example            # Environment variables template
└── README.md
```

---

## Quickstart

### 1. Setup Virtual Environment & Install Dependencies

```bash
cd "wifi-presence"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Initialize the Database

```bash
python3 database/init_db.py
```

This creates the SQLite database at `database/wifi_presence.db` and populates the initial calibrated rooms and access points (`Room 101`, `Room 102`, `Lab 1`).

### 3. Run the Backend Server

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- **API Documentation (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)

### 4. Run Tests

```bash
pytest tests/ -v
```
