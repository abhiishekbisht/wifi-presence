-- Schema for Wi-Fi Presence Estimation System
-- Designed per PRD Section 18

CREATE TABLE IF NOT EXISTS rooms (
    room_id VARCHAR(50) PRIMARY KEY,
    room_name VARCHAR(100) NOT NULL,
    capacity INTEGER NOT NULL,
    building VARCHAR(100),
    floor VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS access_points (
    ap_id VARCHAR(50) PRIMARY KEY,
    room_id VARCHAR(50) NOT NULL,
    ap_name VARCHAR(100),
    status VARCHAR(20) DEFAULT 'online',
    FOREIGN KEY (room_id) REFERENCES rooms(room_id)
);

-- device_id stores an anonymized salted hash of (MAC, SSID). Raw MAC is never stored.
CREATE TABLE IF NOT EXISTS devices (
    device_id VARCHAR(128) PRIMARY KEY,
    first_seen TIMESTAMP NOT NULL,
    last_seen TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    device_id VARCHAR(128) NOT NULL,
    ap_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(20) NOT NULL, -- connect | heartbeat | disconnect
    rssi INTEGER NOT NULL,
    FOREIGN KEY (device_id) REFERENCES devices(device_id),
    FOREIGN KEY (ap_id) REFERENCES access_points(ap_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id VARCHAR(128) NOT NULL,
    ap_id VARCHAR(50) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration REAL DEFAULT 0.0,
    connection_count INTEGER DEFAULT 1,
    avg_rssi REAL,
    rssi_std REAL DEFAULT 0.0,
    active_minutes REAL DEFAULT 0.0,
    ap_transition_count INTEGER DEFAULT 0,
    confidence REAL DEFAULT 0.0,
    dbscan_label VARCHAR(20) DEFAULT 'unassigned', -- core | border | noise | unassigned
    FOREIGN KEY (device_id) REFERENCES devices(device_id),
    FOREIGN KEY (ap_id) REFERENCES access_points(ap_id)
);

CREATE TABLE IF NOT EXISTS attendance_estimates (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id VARCHAR(50) NOT NULL,
    date DATE NOT NULL,
    class_start TIMESTAMP NOT NULL,
    class_end TIMESTAMP NOT NULL,
    active_devices INTEGER DEFAULT 0,
    estimated_presence INTEGER DEFAULT 0,
    occupancy_pct REAL DEFAULT 0.0,
    confidence_avg REAL DEFAULT 0.0,
    FOREIGN KEY (room_id) REFERENCES rooms(room_id)
);

-- Indexes for efficient query access
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_device_id ON events(device_id);
CREATE INDEX IF NOT EXISTS idx_events_ap_id ON events(ap_id);
CREATE INDEX IF NOT EXISTS idx_sessions_device_id ON sessions(device_id);
CREATE INDEX IF NOT EXISTS idx_sessions_ap_id ON sessions(ap_id);
CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time);
CREATE INDEX IF NOT EXISTS idx_attendance_room_date ON attendance_estimates(room_id, date);
