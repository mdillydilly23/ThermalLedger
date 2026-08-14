"""
EVS scoring service.
Computes the Emission Verification Score from satellite estimate vs. reported value.
ADR-003: output shape is EVSScore from shared/evs_schema.py.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../'))

from shared.evs_schema import EVSScore, DiscrepancyFlag


def compute_evs(
    facility_id: str,
    facility_name: str,
    latitude: float,
    longitude: float,
    observation_start: date,
    observation_end: date,
    days_with_valid_retrievals: int,
    total_days: int,
    satellite_ch4_estimate: float,
    satellite_uncertainty_low: float,
    satellite_uncertainty_high: float,
    reported_ch4: Optional[float] = None,
    reported_source: Optional[str] = None,
    reported_year: Optional[int] = None,
) -> EVSScore:
    """
    Compute the EVS score given satellite estimate and reported value.

    EVS = 100 when satellite_ch4 == reported_ch4 exactly.
    EVS approaches 0 as under-reporting grows.
    Flag is determined by sigma_deviation from reported value.
    """
    coverage_pct = (days_with_valid_retrievals / total_days) * 100.0

    delta_pct: Optional[float] = None
    sigma_deviation: Optional[float] = None
    evs: float
    flag: DiscrepancyFlag

    if reported_ch4 is not None and reported_ch4 > 0:
        delta_pct = ((satellite_ch4_estimate - reported_ch4) / reported_ch4) * 100.0

        # Estimate 1σ as half the 95% CI width / 1.96
        sigma = (satellite_uncertainty_high - satellite_uncertainty_low) / (2 * 1.96)
        if sigma > 0:
            sigma_deviation = (satellite_ch4_estimate - reported_ch4) / sigma
        else:
            sigma_deviation = 0.0

        # EVS: penalize exponentially for under-reporting delta
        # A delta of 0% → EVS 100. A delta of +200% → EVS ~18.
        evs = max(0.0, 100.0 * math.exp(-0.008 * max(0.0, delta_pct)))

        if sigma_deviation is not None and sigma_deviation > 2.0:
            flag = DiscrepancyFlag.HIGH
        elif sigma_deviation is not None and sigma_deviation > 1.0:
            flag = DiscrepancyFlag.WATCH
        else:
            flag = DiscrepancyFlag.CLEAR
    else:
        # No reported value to compare — EVS is indeterminate, set to neutral
        evs = 50.0
        flag = DiscrepancyFlag.WATCH

    return EVSScore(
        facility_id=facility_id,
        facility_name=facility_name,
        latitude=latitude,
        longitude=longitude,
        observation_start=observation_start,
        observation_end=observation_end,
        days_with_valid_retrievals=days_with_valid_retrievals,
        coverage_pct=coverage_pct,
        satellite_ch4_estimate=satellite_ch4_estimate,
        satellite_uncertainty_low=satellite_uncertainty_low,
        satellite_uncertainty_high=satellite_uncertainty_high,
        reported_ch4=reported_ch4,
        reported_source=reported_source,
        reported_year=reported_year,
        delta_pct=delta_pct,
        sigma_deviation=sigma_deviation,
        evs=round(evs, 1),
        flag=flag,
    )
