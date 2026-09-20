"""
API route definitions for the Wi-Fi Presence system.
"""
from fastapi import APIRouter
from backend.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint to verify backend service status."""
    return HealthResponse(
        status="healthy",
        service="wifi-presence",
        version="0.1.0"
    )
