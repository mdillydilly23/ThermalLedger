"""Cached ESG parsing task used by the deterministic panel demo."""

from __future__ import annotations

from pathlib import Path

import httpx

from app.core.celery_app import celery_app
from app.core.config import settings
from app.models.api_models import ESGParseResult
from app.services.esg_matcher import match_claims_to_facilities


@celery_app.task(bind=True, name="app.tasks.esg.parse_esg_pdf")
def parse_esg_pdf(self, filename: str, upload_path: str | None = None) -> dict:
    """Ask the ML service to parse an ESG PDF, then match claims to facilities."""
    response: httpx.Response
    if settings.granite_mode == "cached":
        self.update_state(state="PROGRESS", meta={"stage": "Loading cached Granite extraction..."})
        response = httpx.post(
            f"{settings.ml_service_url.rstrip('/')}/granite/parse-cached",
            json={"filename": filename},
            timeout=30,
        )
    else:
        if not upload_path:
            raise RuntimeError("Live ESG parsing requires a stored upload_path.")
        path = Path(upload_path)
        if not path.exists():
            raise FileNotFoundError(f"Stored ESG upload not found: {path}")
        self.update_state(state="PROGRESS", meta={"stage": "Sending PDF to live Granite parser..."})
        with path.open("rb") as handle:
            response = httpx.post(
                f"{settings.ml_service_url.rstrip('/')}/granite/parse",
                files={"file": (filename, handle, "application/pdf")},
                timeout=120,
            )

    response.raise_for_status()
    self.update_state(state="PROGRESS", meta={"stage": "Validating extracted emission claims..."})
    payload = response.json()
    payload["filename"] = filename
    payload["matches"] = match_claims_to_facilities(payload.get("claims", []))
    return ESGParseResult(**payload).model_dump(mode="json")
