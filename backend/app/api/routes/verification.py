"""Live verification run endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.core.celery_app import celery_app
from app.models.api_models import VerificationRunRequest, VerificationRunResponse

router = APIRouter()


@router.post("/runs", response_model=VerificationRunResponse, dependencies=[Depends(require_api_key)])
async def start_verification_run(req: VerificationRunRequest) -> VerificationRunResponse:
    """Start a live Sentinel/ERA5/ML scoring pipeline run."""
    task = celery_app.send_task(
        "app.tasks.verification.run_verification",
        kwargs=req.model_dump(mode="json"),
    )
    return VerificationRunResponse(task_id=task.id)
