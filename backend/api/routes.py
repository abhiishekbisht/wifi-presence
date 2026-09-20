"""
API route definitions for the Wi-Fi Presence system.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Query, Body, Response
from pydantic import BaseModel

from backend.models.schemas import HealthResponse, WiFiEventSchema, RoomSchema, OccupancyResponse
from backend.services.event_service import ingest_event
from backend.services.demo_service import (
    simulate_device_entry,
    simulate_device_exit,
    toggle_ap_status,
    launch_scenario_background,
)
from backend.services.analytics_service import (
    get_historical_analytics,
    get_attendance_by_date,
    export_attendance_csv,
)
from ml.occupancy import compute_room_occupancy, get_all_rooms_occupancy
from database.db import get_db_connection

router = APIRouter()


class DemoActionRequest(BaseModel):
    room_id: str = "Room 101"
    ap_id: Optional[str] = None


class ToggleApRequest(BaseModel):
    ap_id: str = "AP_01"
    status: Optional[str] = None


class RunScenarioRequest(BaseModel):
    scenario: str = "normal_class"
    speed: float = 30.0


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint to verify backend service status."""
    return HealthResponse(
        status="healthy",
        service="wifi-presence",
        version="0.1.0",
    )


@router.post("/events", status_code=status.HTTP_201_CREATED, tags=["Events"])
async def receive_event(event: WiFiEventSchema):
    """
    Ingest a Wi-Fi AP session event (connect, heartbeat, disconnect).
    Validates schema, persists event, updates session features, and broadcasts to WebSocket subscribers.
    """
    try:
        result = await ingest_event(event.model_dump())
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest event: {str(e)}",
        )


@router.get("/rooms", response_model=List[Dict[str, Any]], tags=["Rooms"])
async def get_rooms():
    """List all configured rooms and their associated access points."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rooms")
        rooms = [dict(r) for r in cursor.fetchall()]

        for room in rooms:
            cursor.execute("SELECT * FROM access_points WHERE room_id = ?", (room["room_id"],))
            room["access_points"] = [dict(ap) for ap in cursor.fetchall()]

        return rooms
    finally:
        conn.close()


@router.get("/rooms/{room_id}/occupancy", response_model=OccupancyResponse, tags=["Occupancy"])
async def get_room_occupancy(room_id: str):
    """
    Get current live occupancy estimate, device presence count, and average confidence for a specific room.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT room_id FROM rooms WHERE room_id = ?", (room_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Room '{room_id}' not found.")

        occupancy = compute_room_occupancy(room_id, conn=conn)
        return OccupancyResponse(**occupancy)
    finally:
        conn.close()


@router.get("/occupancy", response_model=List[OccupancyResponse], tags=["Occupancy"])
async def get_all_occupancy():
    """
    Get live occupancy estimates for all configured rooms.
    """
    occupancies = get_all_rooms_occupancy()
    return [OccupancyResponse(**occ) for occ in occupancies]


# ==============================================================================
# ANALYTICS & CSV EXPORT (PRD Section 4 & 19)
# ==============================================================================

@router.get("/analytics", tags=["Analytics"])
async def get_analytics():
    """
    Returns historical analytics: daily attendance trends, room utilization,
    peak occupancy, AP activity distribution, and summary KPIs.
    """
    return get_historical_analytics()


@router.get("/attendance/export/csv", tags=["Analytics"])
async def export_attendance_csv_endpoint(date: Optional[str] = Query(None, description="Optional YYYY-MM-DD filter")):
    """
    Export attendance estimates records as a downloadable CSV file.
    """
    csv_content = export_attendance_csv(date_filter=date)
    filename = f"attendance_estimates_{date}.csv" if date else "attendance_estimates_all.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/attendance/{date}", tags=["Analytics"])
async def get_attendance_date(date: str):
    """
    Get estimated attendance records for a given date (YYYY-MM-DD).
    """
    records = get_attendance_by_date(date)
    return {"date": date, "records": records, "count": len(records)}


# ==============================================================================
# DEMO CONTROLS (PRD Section 20 & Build Prompt Step 6)
# ==============================================================================

@router.post("/demo/simulate-entry", tags=["Demo Controls"])
async def demo_simulate_entry(req: DemoActionRequest = Body(default_factory=DemoActionRequest)):
    """Simulate a single device entering a classroom."""
    return await simulate_device_entry(room_id=req.room_id, ap_id=req.ap_id)


@router.post("/demo/simulate-exit", tags=["Demo Controls"])
async def demo_simulate_exit(req: DemoActionRequest = Body(default_factory=DemoActionRequest)):
    """Simulate an active device leaving a classroom."""
    return await simulate_device_exit(room_id=req.room_id, ap_id=req.ap_id)


@router.post("/demo/toggle-ap", tags=["Demo Controls"])
async def demo_toggle_ap(req: ToggleApRequest = Body(default_factory=ToggleApRequest)):
    """Toggle AP status between online and offline (simulate hardware failure)."""
    return await toggle_ap_status(ap_id=req.ap_id, new_status=req.status)


@router.post("/demo/run-scenario", tags=["Demo Controls"])
async def demo_run_scenario(req: RunScenarioRequest = Body(default_factory=RunScenarioRequest)):
    """Launch a scripted simulation scenario (normal_class, low_attendance, ap_failure)."""
    if req.scenario not in ["normal_class", "low_attendance", "ap_failure"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid scenario. Must be normal_class, low_attendance, or ap_failure",
        )
    launch_scenario_background(scenario_name=req.scenario, speed_multiplier=req.speed)
    return {
        "status": "scenario_started",
        "scenario": req.scenario,
        "speed_multiplier": req.speed,
    }
