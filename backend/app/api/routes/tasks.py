"""
ADR-001: Task status polling endpoint.
Frontend polls this to drive the progress indicator during upload-to-report flow.
"""

from fastapi import APIRouter

from app.core.celery_app import celery_app
from app.models.api_models import TaskStatus

router = APIRouter()

# Maps Celery state names to human-readable progress stages shown in the UI
_STAGE_LABELS = {
    "PENDING": "Queued...",
    "STARTED": "Processing...",
    "SUCCESS": "Complete",
    "FAILURE": "Failed",
}


@router.get("/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str) -> TaskStatus:
    """
    Poll this endpoint to track progress of a background task.
    The `progress_stage` field drives the step-by-step indicator in the demo UI.
    """
    result = celery_app.AsyncResult(task_id)

    if result.state == "FAILURE":
        # Return a typed terminal state so the frontend can stop polling and
        # show the actual failure instead of retrying forever.
        return TaskStatus(
            task_id=task_id,
            status="FAILURE",
            progress_stage=_STAGE_LABELS["FAILURE"],
            error=str(result.info),
        )

    return TaskStatus(
        task_id=task_id,
        status=result.state,
        progress_stage=result.info.get("stage") if isinstance(result.info, dict) else _STAGE_LABELS.get(result.state),
        result=result.result if result.state == "SUCCESS" else None,
    )
