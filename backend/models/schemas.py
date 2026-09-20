from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str = "wifi-presence"
    version: str = "0.1.0"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))



class WiFiEventSchema(BaseModel):
    timestamp: datetime
    ap_id: str
    device_id: str
    event: Literal["connect", "heartbeat", "disconnect"]
    rssi: int


class RoomSchema(BaseModel):
    room_id: str
    room_name: str
    capacity: int
    building: Optional[str] = None
    floor: Optional[str] = None


class AccessPointSchema(BaseModel):
    ap_id: str
    room_id: str
    ap_name: Optional[str] = None
    status: str = "online"
