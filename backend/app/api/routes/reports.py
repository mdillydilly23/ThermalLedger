"""
ADR-001: async def. Long-running report generation dispatched to Celery.
ADR-004: Pydantic request/response models.
ADR-006: Granite report cache — check cache before dispatching Celery task.
"""

from fastapi import APIRouter, HTTPException
from app.models.api_models import ReportRequest, ReportResponse, ReportResult
from app.core.celery_app import celery_app
from app.core.config import settings

router = APIRouter()


@router.post("/generate", response_model=ReportResponse)
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
            "granite_mode": settings.data_source,  # mirrors DATA_SOURCE logic
        },
    )
    return ReportResponse(task_id=task.id, status="processing")


@router.get("/{report_id}", response_model=ReportResult)
async def get_report(report_id: str) -> ReportResult:
    """Fetch a previously generated report by ID."""
    # TODO: load from ml/cache/reports/ or database
    raise NotImplementedError
