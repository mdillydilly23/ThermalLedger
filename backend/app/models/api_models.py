"""
ADR-004: All API response/request shapes as Pydantic models.
These models power the OpenAPI spec that generates frontend TypeScript types.
"""

from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field

# Re-export EVSScore so it appears in the OpenAPI spec under /openapi.json
# Frontend generates src/types/api.ts from this spec (ADR-004).
from shared.evs_schema import EVSScore, DiscrepancyFlag  # noqa: F401


# ── Facilities ────────────────────────────────────────────────

class FacilitySummary(BaseModel):
    facility_id: str
    facility_name: str
    latitude: float
    longitude: float
    sector: str
    latest_evs: Optional[float] = None
    latest_flag: Optional[DiscrepancyFlag] = None


class FacilityListResponse(BaseModel):
    facilities: List[FacilitySummary]
    total: int


# ── ESG Upload ────────────────────────────────────────────────

class ESGClaim(BaseModel):
    company_name: str
    reporting_year: int
    scope1_ch4_tonnes: Optional[float] = None
    scope1_co2e_tonnes: Optional[float] = None
    measurement_methodology: Optional[str] = None
    third_party_verified: bool = False
    source_page: Optional[int] = None


class ESGUploadResponse(BaseModel):
    task_id: str
    filename: str
    status: str = "processing"


class ESGParseResult(BaseModel):
    filename: str
    claims: List[ESGClaim]
    granite_model_id: str
    cached: bool = Field(..., description="True if result served from Granite cache (ADR-006)")


# ── Reports ───────────────────────────────────────────────────

class ReportRequest(BaseModel):
    facility_id: str
    observation_start: date
    observation_end: date


class ReportResponse(BaseModel):
    task_id: str
    status: str = "processing"


class ReportResult(BaseModel):
    report_id: str
    facility_id: str
    report_html: str
    blockchain_tx_id: Optional[str] = None
    cached: bool = Field(..., description="True if served from Granite report cache (ADR-006)")


# ── Task polling (ADR-001: async pattern) ─────────────────────

class TaskStatus(BaseModel):
    task_id: str
    status: str  # pending | started | progress | success | failure
    progress_stage: Optional[str] = None  # e.g. "Parsing document...", "Computing EVS score..."
    result: Optional[dict] = None
    error: Optional[str] = None


# ── Plume ─────────────────────────────────────────────────────

class PlumeGeoJSONResponse(BaseModel):
    facility_id: str
    observation_date: date
    geojson: dict  # GeoJSON FeatureCollection — CH4 column values as point features
