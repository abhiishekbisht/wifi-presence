"""
Main FastAPI Application entrypoint.
"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from backend.config import settings
from backend.api.routes import router as api_router
from database.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database is initialized
    init_db(seed_sample_data=True)
    yield
    # Shutdown logic if needed


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

# Mount API routers
app.include_router(api_router)


@app.get("/")
async def root():
    return {
        "message": "Wi-Fi Classroom Presence Estimation API",
        "docs_url": "/docs",
        "health_url": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
