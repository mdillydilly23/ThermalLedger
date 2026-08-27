"""Granite routes — ESG parsing and report generation."""

from fastapi import APIRouter, UploadFile, File
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
async def parse_esg(file: UploadFile = File(...)):
    """Parse an ESG PDF and return structured emission claims."""
    content = await file.read()
    tmp_path = f"/tmp/{file.filename}"
    with open(tmp_path, "wb") as f:
        f.write(content)
    return await _client.parse_esg_pdf(tmp_path, file.filename or "upload.pdf")


class ReportGenRequest(BaseModel):
    facility_id: str
    evs_data: dict


@router.post("/report")
async def generate_report(req: ReportGenRequest):
    """Generate a Granite verification report for a facility."""
    return await _client.generate_verification_report(req.facility_id, req.evs_data)
