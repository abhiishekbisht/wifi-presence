"""
Main FastAPI Application entrypoint.
"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.api.routes import router as api_router
from backend.websocket.manager import ws_manager
from database.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database is initialized
    init_db(seed_sample_data=True)
    yield
    # Shutdown logic


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Classroom Presence Estimation from Wi-Fi AP Session Logs with Calibrated Room Mapping",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router)


@app.websocket("/live")
async def websocket_live_endpoint(websocket: WebSocket):
    """WebSocket streaming endpoint for live event feed and real-time dashboard updates."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; can accept client commands if needed
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@app.get("/")
async def root():
    return {
        "message": "Wi-Fi Classroom Presence Estimation API",
        "docs_url": "/docs",
        "health_url": "/health",
        "websocket_url": "/live",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
