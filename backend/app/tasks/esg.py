"""Cached ESG parsing task used by the deterministic panel demo."""

from __future__ import annotations

import httpx

from app.core.celery_app import celery_app
from app.core.config import settings


@celery_app.task(bind=True, name="app.tasks.esg.parse_esg_pdf")
def parse_esg_pdf(self, filename: str) -> dict:
    """Ask the ML service for the cached extraction associated with a filename."""
    if settings.granite_mode != "cached":
        raise RuntimeError("Live ESG parsing needs shared object storage and is not enabled in this demo.")

    self.update_state(state="PROGRESS", meta={"stage": "Loading cached Granite extraction..."})
    response = httpx.post(
        f"{settings.ml_service_url.rstrip('/')}/granite/parse-cached",
        json={"filename": filename},
        timeout=30,
    )
    response.raise_for_status()
    self.update_state(state="PROGRESS", meta={"stage": "Validating extracted emission claims..."})
    return response.json()
