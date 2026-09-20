"""
API route definitions for the Wi-Fi Presence system.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Query
from backend.models.schemas import HealthResponse, WiFiEventSchema, RoomSchema, OccupancyResponse
from backend.services.event_service import ingest_event
from ml.occupancy import compute_room_occupancy, get_all_rooms_occupancy
from database.db import get_db_connection

router = APIRouter()


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
