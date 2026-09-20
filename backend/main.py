"""
Main FastAPI Application entrypoint.
Serves REST API, WebSocket streams, and the static NOC Dashboard.
"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings
from backend.api.routes import router as api_router
from backend.websocket.manager import ws_manager
from database.init_db import init_db

DASHBOARD_DIR = PROJECT_ROOT / "dashboard"


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
            # Keep connection alive & receive optional client commands
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# Serve root index.html from dashboard directory
@app.get("/")
async def serve_dashboard():
    index_file = DASHBOARD_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "message": "Wi-Fi Classroom Presence Estimation API",
        "docs_url": "/docs",
        "health_url": "/health",
        "websocket_url": "/live",
    }


# Mount static files for dashboard assets (styles.css, app.js, etc.)
if DASHBOARD_DIR.exists():
    app.mount("/dashboard", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
