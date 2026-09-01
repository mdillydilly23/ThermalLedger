"""Cached verification-report task for the deterministic panel demo."""

from __future__ import annotations

import httpx

from app.core.celery_app import celery_app
from app.core.config import settings
from app.models.api_models import ReportResult
from app.services.audit import anchor_payload
from app.services.parquet_store import get_evs_score


@celery_app.task(bind=True, name="app.tasks.reports.generate_verification_report")
def generate_verification_report(
    self,
    facility_id: str,
    observation_start: str,
    observation_end: str,
) -> dict:
    """Generate or retrieve a verification report using the selected facility EVS."""
    evs_data = get_evs_score(facility_id)
    if evs_data is None:
        raise ValueError(f"Facility '{facility_id}' not found.")

    self.update_state(state="PROGRESS", meta={"stage": "Preparing satellite verification evidence..."})
    response = httpx.post(
        f"{settings.ml_service_url.rstrip('/')}/granite/report",
        json={"facility_id": facility_id, "evs_data": evs_data},
        timeout=120,
    )
    response.raise_for_status()
    result = response.json()
    result["observation_start"] = observation_start
    result["observation_end"] = observation_end
    anchor = anchor_payload("verification_report", result)
    result["blockchain_tx_id"] = anchor["anchor_id"]
    result["audit_mode"] = anchor["mode"]
    self.update_state(state="PROGRESS", meta={"stage": "Finalizing verification report..."})
    return ReportResult(**result).model_dump(mode="json")
