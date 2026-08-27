"""Granite routes — ESG parsing and report generation."""

from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from app.services.granite import GraniteClient

router = APIRouter()
_client = GraniteClient()


class CachedParseRequest(BaseModel):
    filename: str


@router.post("/parse-cached")
async def parse_cached_esg(req: CachedParseRequest):
    """Return a deterministic extraction without persisting the uploaded PDF."""
    return await _client.parse_esg_pdf("", req.filename)


@router.post("/parse")
async def parse_esg(file: UploadFile = File(...)):  # noqa: B008
    """Parse an ESG PDF and return structured emission claims."""
    content = await file.read()
    with NamedTemporaryFile(delete=False, suffix=".pdf") as handle:
        handle.write(content)
        tmp_path = Path(handle.name)
    try:
        return await _client.parse_esg_pdf(str(tmp_path), file.filename or "upload.pdf")
    finally:
        tmp_path.unlink(missing_ok=True)


class ReportGenRequest(BaseModel):
    facility_id: str
    evs_data: dict


@router.post("/report")
async def generate_report(req: ReportGenRequest):
    """Generate a Granite verification report for a facility."""
    return await _client.generate_verification_report(req.facility_id, req.evs_data)
