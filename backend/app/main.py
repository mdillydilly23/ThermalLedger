"""
ADR-001: Async-first backend — all handlers are async def.
ADR-002: DATA_SOURCE toggle wired through Settings.
ADR-004: All responses are Pydantic models; OpenAPI spec auto-generated at /openapi.json.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import esg, facilities, plume, prototype, reports, tasks, verification
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: validate data directory exists when DATA_SOURCE=local
    if settings.data_source == "local" and not settings.data_dir.exists():
        raise RuntimeError(
            f"DATA_SOURCE=local but data directory not found: {settings.data_dir}\n"
            "Run scripts/download_sentinel5p.py and scripts/seed_facilities.py first."
        )
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="ThermalLedger Backend API",
    version="0.1.0",
    description="Satellite emissions verification for corporate carbon credit claims.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(facilities.router, prefix="/facilities", tags=["facilities"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(esg.router, prefix="/esg", tags=["esg"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(plume.router, prefix="/plume", tags=["plume"])
app.include_router(prototype.router, prefix="/prototype", tags=["prototype"])
app.include_router(verification.router, prefix="/verification", tags=["verification"])


@app.get("/health")
async def health():
    return {"status": "ok", "data_source": settings.data_source}
