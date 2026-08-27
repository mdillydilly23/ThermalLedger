"""Cached verification-report task for the deterministic panel demo."""

from __future__ import annotations

import httpx

from app.core.celery_app import celery_app
from app.core.config import settings
from app.services.parquet_store import get_evs_score


@celery_app.task(bind=True, name="app.tasks.reports.generate_verification_report")
def generate_verification_report(
    self,
    facility_id: str,
    observation_start: str,
    observation_end: str,
) -> dict:
    """Generate or retrieve the cached report using the selected facility EVS."""
    if settings.granite_mode != "cached":
        raise RuntimeError("Live report generation is not enabled in this demo.")

    evs_data = get_evs_score(facility_id)
    if evs_data is None:
        raise ValueError(f"Facility '{facility_id}' not found.")

    self.update_state(state="PROGRESS", meta={"stage": "Preparing satellite verification evidence..."})
    response = httpx.post(
        f"{settings.ml_service_url.rstrip('/')}/granite/report",
        json={"facility_id": facility_id, "evs_data": evs_data},
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()
    result["observation_start"] = observation_start
    result["observation_end"] = observation_end
    self.update_state(state="PROGRESS", meta={"stage": "Finalizing cached verification report..."})
    return result
