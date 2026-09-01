"""
backend/app/api/routes/eis.py
──────────────────────────────
E-3: IBM EIS (Environmental Intelligence Suite) API routes.

Exposes:
  GET /eis/status       — whether EIS is configured and reachable
  GET /eis/methane/{facility_id}  — live EIS methane observations for a facility
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.eis_client import get_eis_client
from app.services.parquet_store import get_facility_records

router = APIRouter()


class EISStatus(BaseModel):
    configured: bool
    base_url: str
    message: str


@router.get("/status", response_model=EISStatus)
async def eis_status() -> EISStatus:
    """Return whether the IBM EIS integration is configured."""
    client = get_eis_client()
    if client.is_configured:
        return EISStatus(
            configured=True,
            base_url=client._base_url,
            message="IBM EIS API key is present. Live satellite methane data available.",
        )
    return EISStatus(
        configured=False,
        base_url=client._base_url,
        message="EIS_API_KEY not set. Configure it in .env to enable IBM EIS integration.",
    )


_DEFAULT_START = date(2024, 6, 1)
_DEFAULT_END = date(2024, 6, 30)


@router.get("/methane/{facility_id}")
async def get_eis_methane(
    facility_id: str,
    start: date = Query(default=_DEFAULT_START),  # noqa: B008
    end: date = Query(default=_DEFAULT_END),  # noqa: B008
) -> dict:
    """
    Fetch TROPOMI methane observations from IBM EIS for a single facility.
    Returns 503 when EIS_API_KEY is not configured.
    Returns 502 when the EIS API call fails.
    """
    # Look up facility coordinates from the fixture
    records = get_facility_records([facility_id])
    if not records:
        raise HTTPException(status_code=404, detail=f"Facility '{facility_id}' not found.")

    fac = records[0]
    lat = float(fac["latitude"])
    lon = float(fac["longitude"])

    client = get_eis_client()
    if not client.is_configured:
        raise HTTPException(
            status_code=503,
            detail=(
                "IBM EIS is not configured. Set EIS_API_KEY in your .env file to enable "
                "live Environmental Intelligence Suite satellite data."
            ),
        )

    result = await client.get_methane_observations(
        facility_id=facility_id,
        lat=lat,
        lon=lon,
        start=start,
        end=end,
    )
    if result is None:
        raise HTTPException(
            status_code=502,
            detail="IBM EIS methane query failed. Check logs for details.",
        )
    return result
