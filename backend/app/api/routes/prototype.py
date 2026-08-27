"""Prototype readiness/status endpoints."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
from fastapi import APIRouter

from app.core.config import settings
from app.models.api_models import (
    CredentialStatus,
    DataAvailability,
    PrototypeRunSummary,
    PrototypeStatus,
    ServiceHealth,
)
from app.services.audit import audit_mode, count_jsonl, latest_run

router = APIRouter()


@router.get("/status", response_model=PrototypeStatus)
async def get_prototype_status() -> PrototypeStatus:
    """Return live-prototype readiness for the presentation dashboard."""
    data = _data_availability()
    credentials = _credential_status()
    ml_healthy = await _check_ml_health()
    latest = latest_run()

    missing = []
    if not data.facilities_file:
        missing.append("data/processed/facilities.parquet is missing.")
    if not data.evs_scores_file:
        missing.append("data/processed/evs_scores.parquet is missing.")
    if settings.granite_mode == "live" and not credentials.watsonx:
        missing.append("WATSONX_API_KEY and WATSONX_PROJECT_ID are required for GRANITE_MODE=live.")
    if not credentials.copernicus:
        missing.append("COPERNICUS_USERNAME and COPERNICUS_PASSWORD are required for new Sentinel-5P downloads.")
    if not credentials.cds:
        missing.append("CDS_API_KEY is required for new ERA5 downloads.")
    if not ml_healthy:
        missing.append("ML service is not reachable from the backend.")

    return PrototypeStatus(
        service_health=ServiceHealth(backend=True, ml=ml_healthy),
        credentials=credentials,
        data=data,
        data_source=settings.data_source,
        granite_mode=settings.granite_mode,
        audit_mode=audit_mode(),
        latest_run=PrototypeRunSummary(**latest) if latest else None,
        missing_setup=missing,
    )


def _credential_status() -> CredentialStatus:
    return CredentialStatus(
        copernicus=bool(os.environ.get("COPERNICUS_USERNAME") and os.environ.get("COPERNICUS_PASSWORD")),
        cds=bool(os.environ.get("CDS_API_KEY")),
        watsonx=bool(settings.watsonx_api_key and settings.watsonx_project_id),
        openpages=bool(settings.openpages_base_url and settings.openpages_api_key),
        fabric=bool(settings.fabric_gateway_url),
    )


def _data_availability() -> DataAvailability:
    data_dir = settings.data_dir
    processed = data_dir / "processed"
    return DataAvailability(
        facilities_file=(processed / "facilities.parquet").exists(),
        evs_scores_file=(processed / "evs_scores.parquet").exists(),
        sentinel_raw_count=_count_files(data_dir / "raw" / "sentinel5p", ("*.nc", "*.nc4", "*.zip", "*.SEN3")),
        era5_raw_count=_count_files(data_dir / "raw" / "era5", ("*.nc", "*.grib", "*.grb")),
        processed_plume_count=_count_files(processed / "plumes", ("*.geojson",)),
        upload_count=_count_files(settings.uploads_dir, ("*.pdf",)),
        audit_anchor_count=count_jsonl(settings.audit_dir / "anchors.jsonl"),
        audit_case_count=count_jsonl(settings.audit_dir / "cases.jsonl"),
    )


def _count_files(root: Path, patterns: tuple[str, ...]) -> int:
    if not root.exists():
        return 0
    return sum(1 for pattern in patterns for path in root.rglob(pattern) if path.is_file())


async def _check_ml_health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(f"{settings.ml_service_url.rstrip('/')}/health")
        return response.status_code == 200
    except httpx.HTTPError:
        return False
