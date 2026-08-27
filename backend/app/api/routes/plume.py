"""
Plume GeoJSON endpoint — serves pre-processed CH4 raster as GeoJSON for Deck.gl HeatmapLayer.
ADR-002: Returns an empty FeatureCollection when no processed raster exists locally;
         the frontend HeatmapLayer degrades gracefully with zero points.
"""

import math
from datetime import date

from fastapi import APIRouter, HTTPException

from app.models.api_models import PlumeGeoJSONResponse
from app.services.parquet_store import get_evs_score, get_processed_plume

router = APIRouter()

def _demo_plume(facility_id: str) -> dict:
    """Create a deterministic, clearly labelled visual overlay for the demo.

    This is not a satellite retrieval.  It makes the pipeline legible while
    raw Sentinel-5P processing is unavailable, and is replaced by cached
    GeoJSON once the real attribution pipeline is added.
    """
    score = get_evs_score(facility_id)
    if score is None:
        raise HTTPException(status_code=404, detail=f"Facility '{facility_id}' not found.")

    latitude = float(score["latitude"])
    longitude = float(score["longitude"])
    # Lower EVS means a larger satellite-vs-reported discrepancy, so it is
    # deliberately rendered with a stronger demo plume.
    severity = max(0.35, min(1.0, 1.0 - float(score["evs"]) / 100.0))
    features: list[dict] = []
    # A small eastward Gaussian plume, expressed as weighted point features
    # for the existing Deck.gl HeatmapLayer.
    for y in range(-3, 4):
        for x in range(-2, 7):
            distance = ((x - 1.5) / 3.4) ** 2 + (y / 2.2) ** 2
            weight = math.exp(-distance) * severity
            if weight < 0.06:
                continue
            lat_offset = y * 0.012
            lon_offset = x * 0.014 / max(math.cos(math.radians(latitude)), 0.2)
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [longitude + lon_offset, latitude + lat_offset]},
                "properties": {"weight": round(weight, 4), "source": "deterministic_demo_fixture"},
            })
    return {"type": "FeatureCollection", "features": features}


@router.get("/{facility_id}/geojson", response_model=PlumeGeoJSONResponse)
async def get_plume_geojson(facility_id: str, observation_date: date) -> PlumeGeoJSONResponse:
    """
    Returns a GeoJSON point collection for the Deck.gl HeatmapLayer.
    ADR-005: consumed by FacilityMap HeatmapLayer.
    In deterministic demo mode, returns an explicitly labelled synthetic
    overlay based on the committed fixture score.  Real satellite-processing
    mode will replace it with a cached raster-derived GeoJSON collection.
    """
    processed = get_processed_plume(facility_id, observation_date.isoformat())
    if processed is not None:
        return PlumeGeoJSONResponse(
            facility_id=facility_id,
            observation_date=processed.get("observation_date", observation_date),
            geojson=processed["geojson"],
            source=processed.get("source", "sentinel5p_live_attribution"),
            cached=False,
        )

    return PlumeGeoJSONResponse(
        facility_id=facility_id,
        observation_date=observation_date,
        geojson=_demo_plume(facility_id),
        source="deterministic_demo_fixture",
        cached=True,
    )
