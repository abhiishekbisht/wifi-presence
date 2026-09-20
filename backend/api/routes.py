"""
API route definitions for the Wi-Fi Presence system.
"""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from backend.models.schemas import HealthResponse, WiFiEventSchema, RoomSchema
from backend.services.event_service import ingest_event
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
