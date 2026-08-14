"""Scoring route — internal only, called by backend Celery tasks."""

from fastapi import APIRouter
from pydantic import BaseModel
from datetime import date
from typing import Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../../'))

from shared.evs_schema import EVSScore
from app.services.evs_scorer import compute_evs

router = APIRouter()


class ScoreRequest(BaseModel):
    facility_id: str
    facility_name: str
    latitude: float
    longitude: float
    observation_start: date
    observation_end: date
    days_with_valid_retrievals: int
    total_days: int
    satellite_ch4_estimate: float
    satellite_uncertainty_low: float
    satellite_uncertainty_high: float
    reported_ch4: Optional[float] = None
    reported_source: Optional[str] = None
    reported_year: Optional[int] = None


@router.post("/facility", response_model=EVSScore)
async def score_facility(req: ScoreRequest) -> EVSScore:
    """Compute EVS score for a facility. Called by backend — not exposed to browser."""
    return compute_evs(**req.model_dump())
