"""
ADR-001: async def. Long-running report generation dispatched to Celery.
ADR-004: Pydantic request/response models.
ADR-006: Granite report cache — check cache before dispatching Celery task.
"""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_api_key
from app.core.celery_app import celery_app
from app.core.config import settings
from app.models.api_models import ReportRequest, ReportResponse, ReportResult

router = APIRouter()


@router.post("/generate", response_model=ReportResponse, dependencies=[Depends(require_api_key)])
async def generate_report(req: ReportRequest) -> ReportResponse:
    """
    Trigger Granite report generation for a facility.
    Returns task_id immediately — poll GET /tasks/{task_id} for result.
    ADR-001: never blocks on Granite call.
    ADR-006: if GRANITE_MODE=cached, task completes instantly from cache.
    """
    task = celery_app.send_task(
        "app.tasks.reports.generate_verification_report",
        kwargs={
            "facility_id": req.facility_id,
            "observation_start": req.observation_start.isoformat(),
            "observation_end": req.observation_end.isoformat(),
        },
    )
    return ReportResponse(task_id=task.id, status="processing")


@router.get("/{report_id}", response_model=ReportResult)
async def get_report(report_id: str) -> ReportResult:
    """Fetch a previously generated report by ID."""
    if report_id.startswith("cached_"):
        facility_id = Path(report_id.removeprefix("cached_")).name
        report_file = settings.reports_cache_dir / f"{facility_id}_report.html"
        if not report_file.exists():
            report_file = settings.reports_cache_dir / "hero_facility_report.html"
        if not report_file.exists():
            raise HTTPException(status_code=404, detail="Cached report asset not found.")
        return ReportResult(
            report_id=report_id,
            facility_id=facility_id,
            report_html=report_file.read_text(encoding="utf-8"),
            cached=True,
        )

    # For live-generated reports, search the audit trail JSONL for a matching report_id.
    anchors_path = settings.audit_dir / "anchors.jsonl"
    if anchors_path.exists():
        with anchors_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = record.get("payload", {})
                if payload.get("report_id") == report_id:
                    report_html = payload.get("report_html")
                    facility_id = payload.get("facility_id", "")
                    if report_html:
                        return ReportResult(
                            report_id=report_id,
                            facility_id=facility_id,
                            report_html=report_html,
                            cached=False,
                        )

    raise HTTPException(
        status_code=404,
        detail=f"Report '{report_id}' not found. Live reports are available only while the audit trail is present.",
    )
