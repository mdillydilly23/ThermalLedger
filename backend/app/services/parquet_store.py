"""
backend/app/services/parquet_store.py
───────────────────────────────────────
Read-only access to the two demo Parquet files produced by
scripts/write_demo_parquet.py.

ADR-002: Only used when DATA_SOURCE=local.
ADR-003: Returns shared EVSScore / FacilitySummary shapes.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

from app.core.config import settings


def _facilities_path() -> Path:
    return settings.data_dir / "processed" / "facilities.parquet"


def _scores_path() -> Path:
    return settings.data_dir / "processed" / "evs_scores.parquet"


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
    """
    fac = _load_facilities()
    scores = _load_scores()[["facility_id", "evs", "flag"]].rename(
        columns={"evs": "latest_evs", "flag": "latest_flag"}
    )
    merged = fac.merge(scores, on="facility_id", how="left")
    return merged.to_dict(orient="records")


def get_evs_score(facility_id: str) -> Optional[dict]:
    """
    Return the full EVS score row for a single facility, or None if not found.
    Shape matches EVSScore in shared/evs_schema.py.
    """
    scores = _load_scores()
    row = scores[scores["facility_id"] == facility_id]
    if row.empty:
        return None
    record = row.iloc[0].to_dict()
    # Replace NaN with None so Pydantic can serialise correctly
    return {k: (None if pd.isna(v) else v) for k, v in record.items()}
