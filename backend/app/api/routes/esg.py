"""
ADR-001: async def. PDF upload dispatched to Celery — never blocks.
ADR-006: Granite parsing result served from cache when GRANITE_MODE=cached.
"""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.celery_app import celery_app
from app.core.config import settings
from app.models.api_models import ESGUploadResponse

router = APIRouter()
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("/upload", response_model=ESGUploadResponse)
async def upload_esg_pdf(file: UploadFile = File(...)) -> ESGUploadResponse:  # noqa: B008
    """
    Accept a corporate ESG PDF and dispatch Granite parsing as a background task.
    Returns task_id — poll GET /tasks/{task_id} for the parsed ESGParseResult.
    Demo: task completes immediately from cache when GRANITE_MODE=cached (ADR-006).
    """
    filename = Path(file.filename or "upload.pdf").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF files are accepted.")

    # Read once to enforce a sensible prototype limit, then persist so the
    # worker can send the PDF to Granite in live mode.  A production deployment
    # should replace this with object storage and malware scanning.
    content = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="PDF must be 10 MB or smaller.")

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}_{filename}"
    upload_path = settings.uploads_dir / stored_name
    upload_path.write_bytes(content)

    task = celery_app.send_task(
        "app.tasks.esg.parse_esg_pdf",
        kwargs={"filename": filename, "upload_path": str(upload_path)},
    )
    return ESGUploadResponse(task_id=task.id, filename=filename)
