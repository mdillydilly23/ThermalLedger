"""Plume model route — Sentinel/ERA5 attribution, internal only."""

from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel
from shared.evs_schema import EVSScore

from app.services.plume_attribution import attribute_facility

router = APIRouter()


class PlumeAttributionRequest(BaseModel):
    facility_id: str
    facility_name: str
    latitude: float
    longitude: float
    start: date
    end: date
    reported_ch4: float | None = None
    reported_source: str | None = None
    reported_year: int | None = None


class PlumeAttributionResponse(BaseModel):
    facility_id: str
    source: str
    method_notes: list[str]
    score: EVSScore
    geojson: dict


@router.post("/attribute", response_model=PlumeAttributionResponse)
async def attribute_plume(req: PlumeAttributionRequest) -> PlumeAttributionResponse:
    """
    Attribute satellite CH4 to a facility using local Sentinel-5P and ERA5 files.
    """
    return PlumeAttributionResponse(**attribute_facility(**req.model_dump()))
