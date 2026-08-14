"""
ADR-001: async def. PDF upload dispatched to Celery — never blocks.
ADR-006: Granite parsing result served from cache when GRANITE_MODE=cached.
"""

from fastapi import APIRouter, UploadFile, File
from app.models.api_models import ESGUploadResponse
from app.core.celery_app import celery_app

router = APIRouter()


@router.post("/upload", response_model=ESGUploadResponse)
async def upload_esg_pdf(file: UploadFile = File(...)) -> ESGUploadResponse:
    """
    Accept a corporate ESG PDF and dispatch Granite parsing as a background task.
    Returns task_id — poll GET /tasks/{task_id} for the parsed ESGParseResult.
    Demo: task completes immediately from cache when GRANITE_MODE=cached (ADR-006).
    """
    # Save upload to a temp path — Celery worker reads from there
    content = await file.read()
    tmp_path = f"/tmp/esg_upload_{file.filename}"
    with open(tmp_path, "wb") as f:
        f.write(content)

    task = celery_app.send_task(
        "app.tasks.esg.parse_esg_pdf",
        kwargs={"pdf_path": tmp_path, "filename": file.filename},
    )
    return ESGUploadResponse(task_id=task.id, filename=file.filename or "upload.pdf")
