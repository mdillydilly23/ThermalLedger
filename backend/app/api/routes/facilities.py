"""
ADR-001: async def handlers only.
ADR-002: DATA_SOURCE=local reads from Parquet files in data/processed/.
ADR-004: responses typed as Pydantic models.
"""

from fastapi import APIRouter, HTTPException

from app.models.api_models import EVSScore, FacilityListResponse, FacilitySummary
from app.services.parquet_store import get_evs_score, get_facility_summaries

router = APIRouter()


@router.get("", response_model=FacilityListResponse)
async def list_facilities() -> FacilityListResponse:
    """
    Return all facilities with their latest EVS score.
    Powers the map markers on the frontend dashboard.
    ADR-002: loaded from data/processed/facilities.parquet + evs_scores.parquet.
    """
    rows = get_facility_summaries()
    facilities = [FacilitySummary(**r) for r in rows]
    return FacilityListResponse(facilities=facilities, total=len(facilities))


@router.get("/{facility_id}", response_model=EVSScore)
async def get_facility_detail(facility_id: str) -> EVSScore:
    """
    Full EVS detail for one facility — satellite estimate, reported value,
    discrepancy score.
    ADR-002: loaded from data/processed/evs_scores.parquet.
    """
    record = get_evs_score(facility_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Facility '{facility_id}' not found.")
    return EVSScore(**record)
