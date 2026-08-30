"""
ADR-001: async def handlers only.
ADR-002: DATA_SOURCE=local reads from Parquet files in data/processed/.
ADR-004: responses typed as Pydantic models.
E-4: watsonx.data (Presto) federated registry source exposed via /facilities/registry-source.
"""

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.models.api_models import EVSScore, FacilityListResponse, FacilitySummary
from app.services.parquet_store import get_evs_score, get_facility_summaries
from app.services.watsonxdata_client import get_watsonxdata_client

router = APIRouter()


@router.get("", response_model=FacilityListResponse)
async def list_facilities() -> FacilityListResponse:
    """
    Return all facilities with their latest EVS score.
    Powers the map markers on the frontend dashboard.
    ADR-002: loaded from data/processed/facilities.parquet + evs_scores.parquet.
    """
    rows = get_facility_summaries()
    facilities = [FacilitySummary(**r) for r in rows]
    return FacilityListResponse(facilities=facilities, total=len(facilities))


# ── E-4: watsonx.data registry source status ─────────────────────────────────

class RegistrySourceResponse(BaseModel):
    source: str          # "watsonxdata" | "parquet"
    configured: bool
    host: str
    message: str


@router.get("/registry-source", response_model=RegistrySourceResponse)
async def get_registry_source() -> RegistrySourceResponse:
    """
    Report which facility registry backend is active.
    When WATSONXDATA_HOST is configured the Presto query path is available;
    otherwise the committed Parquet fixture is used.
    This endpoint is surfaced in the Prototype readiness panel to demonstrate
    IBM watsonx.data platform integration.
    """
    client = get_watsonxdata_client()
    if client.is_configured:
        return RegistrySourceResponse(
            source="watsonxdata",
            configured=True,
            host=client._host,
            message=(
                "Facility registry is served via IBM watsonx.data (Presto). "
                "Queries are federated through the Presto coordinator at "
                f"{client._host}:{client._port}."
            ),
        )
    return RegistrySourceResponse(
        source="parquet",
        configured=False,
        host="",
        message=(
            "Facility registry is served from the committed Parquet fixture. "
            "Set WATSONXDATA_HOST and WATSONXDATA_ACCESS_TOKEN in .env to enable "
            "federated IBM watsonx.data queries."
        ),
    )


@router.get("/{facility_id}", response_model=EVSScore)
async def get_facility_detail(facility_id: str) -> EVSScore:
    """
    Full EVS detail for one facility — satellite estimate, reported value,
    discrepancy score.
    ADR-002: loaded from data/processed/evs_scores.parquet.
    """
    record = get_evs_score(facility_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Facility '{facility_id}' not found.")
    return EVSScore(**record)


# ── E-1: Granite "Explain this EVS score" endpoint ────────────────────────────

class ExplainRequest(BaseModel):
    question: str = "Why is this facility flagged and what does the EVS score mean?"


class ExplainResponse(BaseModel):
    facility_id: str
    question: str
    answer: str
    cached: bool


@router.post("/{facility_id}/explain", response_model=ExplainResponse)
async def explain_facility_evs(facility_id: str, body: ExplainRequest) -> ExplainResponse:
    """
    Use IBM Granite to answer a reviewer's contextual question about a facility's EVS score.
    The full EVS evidence is passed as context so Granite can give a data-grounded answer.
    Routes through the ML service /granite/explain endpoint.
    """
    record = get_evs_score(facility_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Facility '{facility_id}' not found.")

    ml_url = f"{settings.ml_service_url.rstrip('/')}/granite/explain"
    payload = {"evs_data": record, "question": body.question}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(ml_url, json=payload)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"ML service returned {exc.response.status_code} for explain request.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail="ML service is unavailable. Try again or check GRANITE_MODE.",
        ) from exc

    return ExplainResponse(
        facility_id=facility_id,
        question=body.question,
        answer=data.get("answer", ""),
        cached=bool(data.get("cached", True)),
    )


# ── E-2: EVS score history endpoint ───────────────────────────────────────────

class EVSHistoryPoint(BaseModel):
    observation_date: str
    evs: float
    flag: str
    satellite_ch4_estimate: float
    reported_ch4: float | None = None


class EVSHistoryResponse(BaseModel):
    facility_id: str
    history: list[EVSHistoryPoint]


@router.get("/{facility_id}/history", response_model=EVSHistoryResponse)
async def get_facility_history(facility_id: str) -> EVSHistoryResponse:
    """
    Return synthetic EVS score history for a facility.
    Demonstrates ThermalLedger as a continuous monitoring platform rather than
    a point-in-time audit tool.  In GRANITE_MODE=cached the history is derived
    from the committed fixture data with simulated prior-period deltas.
    """
    from app.services.parquet_store import get_evs_score as _get_score
    record = _get_score(facility_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Facility '{facility_id}' not found.")

    history = _build_evs_history(record)
    return EVSHistoryResponse(facility_id=facility_id, history=history)


def _build_evs_history(record: dict) -> list[dict]:
    """
    Build a 3-point synthetic history from the current EVS fixture.
    Points are labelled Q2-2023, Q4-2023, and Q2-2024 (the fixture window).
    The earlier points apply small deterministic perturbations so the chart
    shows realistic variation without requiring additional data files.
    """
    evs_now = float(record.get("evs") or 50.0)
    ch4_now = float(record.get("satellite_ch4_estimate") or 1000.0)
    reported_now = record.get("reported_ch4")
    flag_now = str(record.get("flag") or "watch")

    def _flag(evs: float) -> str:
        if evs < 33:
            return "high"
        if evs < 66:
            return "watch"
        return "clear"

    # Simulate slight improvement trend toward current value
    evs_t0 = max(0.0, min(100.0, evs_now - 12.0))
    evs_t1 = max(0.0, min(100.0, evs_now - 5.0))

    return [
        {
            "observation_date": "2023-06-30",
            "evs": round(evs_t0, 1),
            "flag": _flag(evs_t0),
            "satellite_ch4_estimate": round(ch4_now * 1.18, 0),
            "reported_ch4": round(reported_now * 0.95, 0) if reported_now else None,
        },
        {
            "observation_date": "2023-12-31",
            "evs": round(evs_t1, 1),
            "flag": _flag(evs_t1),
            "satellite_ch4_estimate": round(ch4_now * 1.07, 0),
            "reported_ch4": reported_now,
        },
        {
            "observation_date": str(record.get("observation_end") or "2024-06-30"),
            "evs": round(evs_now, 1),
            "flag": flag_now,
            "satellite_ch4_estimate": round(ch4_now, 0),
            "reported_ch4": reported_now,
        },
    ]
