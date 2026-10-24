"""Main App Store FastAPI application.

Sits alongside the Pick'em app (nflpi). Uses its own SQLite database,
its own token-based auth, its own installer boundary. Served privately
via Tailscale Serve on the tailnet.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import text

from app_store.config import get_settings
from app_store.db import get_engine, init_db
from app_store.routers import include_in_app
from app_store.routers import schemas as s

# Module-level app for uvicorn
app = FastAPI(
    title="App Store",
    description="Private app marketplace for the Tailscale network. Tailnet-only.",
    version="0.1.0",
)

# Allow cross-origin for the admin UI (passkey browser)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://localhost", "http://localhost", "https://127.0.0.1", "http://127.0.0.1"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database initialization (lifespan)
@asynccontextmanager
async def lifespan(app_obj: FastAPI):
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
    init_db()
    yield

app.state.lifespan = lifespan


# Include API routers
include_in_app(app)

# Serve static files if present (admin UI)
_static_dir = Path(__file__).resolve().parent.parent / "web" / "out"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
    @app.get("/", include_in_schema=False)
    async def root():
        index = _static_dir / "index.html"
        if index.exists():
            return FileResponse(index)
        return {"status": "ok", "database": True, "message": "App Store API is running. Use /api/store/... endpoints."}
