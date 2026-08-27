"""
ADR-001: async def. PDF upload dispatched to Celery — never blocks.
ADR-006: Granite parsing result served from cache when GRANITE_MODE=cached.
"""

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from app.models.api_models import ESGUploadResponse
from app.core.celery_app import celery_app

router = APIRouter()
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("/upload", response_model=ESGUploadResponse)
async def upload_esg_pdf(file: UploadFile = File(...)) -> ESGUploadResponse:
    """
    Accept a corporate ESG PDF and dispatch Granite parsing as a background task.
    Returns task_id — poll GET /tasks/{task_id} for the parsed ESGParseResult.
    Demo: task completes immediately from cache when GRANITE_MODE=cached (ADR-006).
    """
    filename = Path(file.filename or "upload.pdf").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF files are accepted.")

    # The panel demo intentionally uses the committed Granite cache.  Read only
    # enough to enforce a sensible limit; no untrusted file is written into the
    # API or worker container.  A live deployment should replace this with
    # object storage and a malware-scanning step.
    content = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="PDF must be 10 MB or smaller.")

    task = celery_app.send_task(
        "app.tasks.esg.parse_esg_pdf",
        kwargs={"filename": filename},
    )
    return ESGUploadResponse(task_id=task.id, filename=filename)
