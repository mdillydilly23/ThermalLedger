"""
Plume GeoJSON endpoint — serves pre-processed CH4 raster as GeoJSON for Deck.gl HeatmapLayer.
ADR-002: Returns an empty FeatureCollection when no processed raster exists locally;
         the frontend HeatmapLayer degrades gracefully with zero points.
"""

from datetime import date
from fastapi import APIRouter
from app.models.api_models import PlumeGeoJSONResponse

router = APIRouter()

# Empty GeoJSON FeatureCollection — safe default until real rasters are processed.
_EMPTY_FC: dict = {"type": "FeatureCollection", "features": []}


@router.get("/{facility_id}/geojson", response_model=PlumeGeoJSONResponse)
async def get_plume_geojson(facility_id: str, observation_date: date) -> PlumeGeoJSONResponse:
    """
    Returns CH4 column values as a GeoJSON FeatureCollection for Deck.gl HeatmapLayer.
    ADR-005: consumed by FacilityMap HeatmapLayer.
    ADR-002: returns empty FeatureCollection when no raster is available locally;
             the map renders without a plume overlay rather than returning 500.
    TODO: load from pre-processed GeoJSON cache in data/processed/ once rasters are ingested.
    """
    return PlumeGeoJSONResponse(
        facility_id=facility_id,
        observation_date=observation_date,
        geojson=_EMPTY_FC,
    )
