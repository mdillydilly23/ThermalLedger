"""
backend/app/services/parquet_store.py
───────────────────────────────────────
Read-only access to the two demo Parquet files produced by
scripts/write_demo_parquet.py.

ADR-002: Only used when DATA_SOURCE=local.
ADR-003: Returns shared EVSScore / FacilitySummary shapes.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.core.config import settings


def _facilities_path() -> Path:
    return settings.data_dir / "processed" / "facilities.parquet"


def _scores_path() -> Path:
    return settings.data_dir / "processed" / "evs_scores.parquet"


def _plumes_dir() -> Path:
    return settings.data_dir / "processed" / "plumes"


# ── Cached loaders (file read once per process) ───────────────────────────────

@lru_cache(maxsize=1)
def _load_facilities() -> pd.DataFrame:
    return pd.read_parquet(_facilities_path())


@lru_cache(maxsize=1)
def _load_scores() -> pd.DataFrame:
    return pd.read_parquet(_scores_path())


# ── Public API ────────────────────────────────────────────────────────────────

def get_facility_summaries() -> list[dict]:
    """
    Return all facilities joined with their latest EVS score.
    Shape matches FacilitySummary in api_models.py.
    Returns an empty list if the fixture files are missing (graceful degradation).
    """
    if not _facilities_path().exists() or not _scores_path().exists():
        return []
    fac = _load_facilities()
    scores = _load_scores()[["facility_id", "evs", "flag"]].rename(
        columns={"evs": "latest_evs", "flag": "latest_flag"}
    )
    merged = fac.merge(scores, on="facility_id", how="left")
    return _records_without_nan(merged)


def get_facility_records(facility_ids: list[str] | None = None) -> list[dict]:
    """Return facility rows, optionally filtered to the requested identifiers."""
    fac = _load_facilities()
    if facility_ids:
        fac = fac[fac["facility_id"].isin(facility_ids)]
    return _records_without_nan(fac)


def get_evs_score(facility_id: str) -> dict | None:
    """
    Return the full EVS score row for a single facility, or None if not found.
    Shape matches EVSScore in shared/evs_schema.py.
    """
    scores = _load_scores()
    row = scores[scores["facility_id"] == facility_id]
    if row.empty:
        return None
    return _record_without_nan(row.iloc[0].to_dict())


def get_all_evs_scores() -> list[dict]:
    """Return all EVS rows."""
    return _records_without_nan(_load_scores())


def upsert_evs_scores(records: list[dict]) -> int:
    """
    Atomically upsert EVS score records into data/processed/evs_scores.parquet.

    The live prototype runs in one Celery worker process by default; this keeps
    the file write simple while still avoiding partially written Parquet files.
    """
    if not records:
        return 0

    processed_dir = _scores_path().parent
    processed_dir.mkdir(parents=True, exist_ok=True)

    existing = _load_scores() if _scores_path().exists() else pd.DataFrame()
    incoming = pd.DataFrame(records)
    if "facility_id" not in incoming.columns:
        raise ValueError("EVS records must include facility_id.")

    if existing.empty:
        merged = incoming
    else:
        existing = existing[~existing["facility_id"].isin(incoming["facility_id"])]
        merged = pd.concat([existing, incoming], ignore_index=True, sort=False)

    tmp_path = _scores_path().with_suffix(".parquet.tmp")
    merged.to_parquet(tmp_path, index=False)
    os.replace(tmp_path, _scores_path())
    _load_scores.cache_clear()  # scores file was rewritten; invalidate scores cache only
    return len(incoming)


def plume_path(facility_id: str, observation_date: str) -> Path:
    """Return the processed plume cache path for a facility/date."""
    safe_facility_id = Path(facility_id).name
    safe_date = observation_date.replace("/", "-")
    return _plumes_dir() / f"{safe_facility_id}_{safe_date}.geojson"


def write_processed_plume(
    facility_id: str,
    observation_date: str,
    geojson: dict,
    source: str,
) -> Path:
    """Persist live plume GeoJSON with source metadata."""
    path = plume_path(facility_id, observation_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "facility_id": facility_id,
        "observation_date": observation_date,
        "source": source,
        "geojson": geojson,
    }
    tmp_path = path.with_suffix(".geojson.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp_path, path)
    return path


def get_processed_plume(facility_id: str, observation_date: str) -> dict | None:
    """Load processed live plume GeoJSON if present."""
    path = plume_path(facility_id, observation_date)
    if not path.exists():
        safe_facility_id = Path(facility_id).name
        candidates = sorted(
            _plumes_dir().glob(f"{safe_facility_id}_*.geojson"),
            key=lambda candidate: candidate.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return None
        path = candidates[0]
    return json.loads(path.read_text(encoding="utf-8"))


def _record_without_nan(record: dict) -> dict:
    """Replace pandas/NumPy NaN values with None for JSON/Pydantic output."""
    cleaned: dict = {}
    for key, value in record.items():
        if isinstance(value, (list, tuple, dict)):
            cleaned[key] = value
            continue
        cleaned[key] = None if pd.isna(value) else value
    return cleaned


def _records_without_nan(frame: pd.DataFrame) -> list[dict]:
    return [_record_without_nan(record) for record in frame.to_dict(orient="records")]
