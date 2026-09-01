"""
ADR-003: EVS Shared Schema — single source of truth for the Emission Verification Score.

This module is imported by both `backend` and `ml` services.
The frontend TypeScript equivalent is generated from the backend's OpenAPI spec (ADR-004).

Never define EVSScore inline elsewhere — always import from here.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DiscrepancyFlag(str, Enum):
    CLEAR = "clear"   # satellite ≈ reported  (within 1σ)
    WATCH = "watch"   # satellite > reported  (1–2σ)
    HIGH = "high"     # satellite >> reported (>2σ) — triggers OpenPages GRC workflow


class EVSScore(BaseModel):
    """
    Core Emission Verification Score object.
    All CH4 values are in tonnes/year unless noted.
    """

    # ── Identity ──────────────────────────────────────────────
    facility_id: str = Field(..., description="EU ETS or EPA GHGRP facility identifier")
    facility_name: str
    latitude: float
    longitude: float

    # ── Observation window ────────────────────────────────────
    observation_start: date
    observation_end: date
    days_with_valid_retrievals: int = Field(
        ..., description="Days in window with QA-passing TROPOMI data"
    )
    coverage_pct: float = Field(
        ..., ge=0.0, le=100.0, description="% of window days with valid retrievals"
    )
    total_days: int = Field(
        0, description="Total calendar days in the observation window"
    )

    # ── Satellite-derived estimate ────────────────────────────
    satellite_ch4_estimate: float = Field(
        ..., description="Satellite-derived CH4, tonnes/year (30-day temporal ensemble)"
    )
    satellite_uncertainty_low: float = Field(
        ..., description="Lower bound of 95% confidence interval"
    )
    satellite_uncertainty_high: float = Field(
        ..., description="Upper bound of 95% confidence interval"
    )

    # ── Corporate self-reported value ─────────────────────────
    reported_ch4: Optional[float] = Field(
        None, description="Corporate-reported Scope 1 CH4, tonnes/year"
    )
    reported_source: Optional[str] = Field(
        None, description="Source document — ESG PDF filename or registry name"
    )
    reported_year: Optional[int] = None

    # ── Scoring ───────────────────────────────────────────────
    delta_pct: Optional[float] = Field(
        None,
        description="((satellite − reported) / reported) × 100. Positive = under-reporting.",
    )
    sigma_deviation: Optional[float] = Field(
        None,
        description="Standard deviations by which satellite estimate exceeds reported value.",
    )
    evs: float = Field(
        ..., ge=0.0, le=100.0,
        description="Emission Verification Score 0–100. 100 = perfect satellite/report alignment.",
    )
    flag: DiscrepancyFlag

    # ── Audit trail ───────────────────────────────────────────
    blockchain_tx_id: Optional[str] = Field(
        None, description="Hyperledger Fabric tx hash, set after anchoring"
    )
    report_id: Optional[str] = Field(
        None, description="Generated Granite verification report ID"
    )
