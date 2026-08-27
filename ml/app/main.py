"""
ML service entry point.
ADR-001: async def throughout.
ADR-002: DATA_SOURCE toggle (reads local satellite data vs live API).
ADR-006: GRANITE_MODE toggle (cached vs live Granite calls).
"""

from fastapi import FastAPI

from app.api.routes import granite, plume_model, score

app = FastAPI(
    title="ThermalLedger ML Service",
    version="0.1.0",
    description="Plume attribution, EVS scoring, Granite ESG parsing and report generation.",
)

app.include_router(score.router, prefix="/score", tags=["scoring"])
app.include_router(granite.router, prefix="/granite", tags=["granite"])
app.include_router(plume_model.router, prefix="/plume", tags=["plume"])


@app.get("/health")
async def health():
    return {"status": "ok"}
