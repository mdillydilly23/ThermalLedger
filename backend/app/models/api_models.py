"""
ADR-004: All API response/request shapes as Pydantic models.
These models power the OpenAPI spec that generates frontend TypeScript types.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# Re-export EVSScore so it appears in the OpenAPI spec under /openapi.json
# Frontend generates src/types/api.ts from this spec (ADR-004).
from shared.evs_schema import DiscrepancyFlag, EVSScore  # noqa: F401

# ── Facilities ────────────────────────────────────────────────

class FacilitySummary(BaseModel):
    facility_id: str
    facility_name: str
    latitude: float
    longitude: float
    sector: str
    latest_evs: float | None = None
    latest_flag: DiscrepancyFlag | None = None


class FacilityListResponse(BaseModel):
    facilities: list[FacilitySummary]
    total: int


# ── ESG Upload ────────────────────────────────────────────────

class ESGClaim(BaseModel):
    company_name: str
    reporting_year: int
    scope1_ch4_tonnes: float | None = None
    scope1_co2e_tonnes: float | None = None
    measurement_methodology: str | None = None
    third_party_verified: bool = False
    source_page: int | None = None


class ESGClaimMatch(BaseModel):
    facility_id: str
    facility_name: str
    claim_year: int | None = None
    reported_ch4: float | None = None
    latest_evs: float | None = None
    latest_flag: DiscrepancyFlag | None = None
    match_reason: str | None = None


class ESGUploadResponse(BaseModel):
    task_id: str
    filename: str
    status: str = "processing"


class ESGParseResult(BaseModel):
    filename: str
    claims: list[ESGClaim]
    granite_model_id: str
    cached: bool = Field(..., description="True if result served from Granite cache (ADR-006)")
    matches: list[ESGClaimMatch] = Field(default_factory=list)


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
    blockchain_tx_id: str | None = None
    audit_mode: str | None = None
    cached: bool = Field(..., description="True if served from Granite report cache (ADR-006)")


# ── Task polling (ADR-001: async pattern) ─────────────────────

class TaskStatus(BaseModel):
    task_id: str
    status: str  # pending | started | progress | success | failure
    progress_stage: str | None = None  # e.g. "Parsing document...", "Computing EVS score..."
    result: dict | None = None
    error: str | None = None


# ── Plume ─────────────────────────────────────────────────────

class PlumeGeoJSONResponse(BaseModel):
    facility_id: str
    observation_date: date
    geojson: dict  # GeoJSON FeatureCollection — CH4 column values as point features
    source: str = "deterministic_demo_fixture"
    cached: bool = True


# ── Live prototype status and verification runs ─────────────────

class VerificationRunRequest(BaseModel):
    facility_ids: list[str] | None = None
    start_date: date
    end_date: date
    bbox: list[float] | None = Field(
        default=None,
        min_length=4,
        max_length=4,
        description="Bounding box [west, south, east, north].",
    )
    reuse_existing_raw_data: bool = True


class VerificationRunResponse(BaseModel):
    task_id: str
    status: str = "processing"


class CredentialStatus(BaseModel):
    copernicus: bool
    cds: bool
    watsonx: bool
    openpages: bool
    fabric: bool


class DataAvailability(BaseModel):
    facilities_file: bool
    evs_scores_file: bool
    sentinel_raw_count: int
    era5_raw_count: int
    processed_plume_count: int
    upload_count: int
    audit_anchor_count: int
    audit_case_count: int


class ServiceHealth(BaseModel):
    backend: bool
    ml: bool


class PrototypeRunSummary(BaseModel):
    run_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    facility_count: int = 0
    observation_start: date
    observation_end: date
    source: str
    task_id: str | None = None
    error: str | None = None


class PrototypeStatus(BaseModel):
    service_health: ServiceHealth
    credentials: CredentialStatus
    data: DataAvailability
    data_source: Literal["local", "remote"]
    granite_mode: Literal["cached", "live"]
    audit_mode: Literal["local_audit_fallback", "live_fabric"]
    latest_run: PrototypeRunSummary | None = None
    missing_setup: list[str] = Field(default_factory=list)
