#!/usr/bin/env python3
"""
scripts/write_demo_parquet.py
──────────────────────────────
One-shot script: reads data/fixtures/registry.csv and writes two Parquet
files consumed by the backend at runtime (DATA_SOURCE=local).

Output
------
data/processed/facilities.parquet   – facility master table
data/processed/evs_scores.parquet   – one pre-computed EVS score per facility

The EVS scores are deterministically derived from the registry's
reported_ch4_kt column so the demo always returns consistent, meaningful
numbers without hitting any external API.

Usage
-----
    python scripts/write_demo_parquet.py
"""

from __future__ import annotations

import math
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures" / "registry.csv"
PROCESSED = ROOT / "data" / "processed"

# Observation window used for all demo scores
OBS_END = date(2024, 6, 30)
OBS_START = OBS_END - timedelta(days=29)   # 30-day window
TOTAL_DAYS = 30


def _satellite_estimate(reported_ch4_kt: float | None) -> tuple[float, float, float]:
    """
    Fabricate a plausible satellite CH4 estimate from the reported value.
    Returns (estimate, low_95ci, high_95ci) in tonnes/year.

    Intentionally introduces a realistic mix of CLEAR / WATCH / HIGH flags:
      ~40% clear  (satellite ≈ reported)
      ~35% watch  (satellite 1-2σ above reported)
      ~25% high   (satellite >2σ above reported)
    """
    if reported_ch4_kt is None or reported_ch4_kt <= 0:
        # No reported value — return a neutral estimate
        base_t = 5_000.0
        sigma = base_t * 0.15
        return base_t, base_t - 1.96 * sigma, base_t + 1.96 * sigma

    base_t = reported_ch4_kt * 1_000.0   # kt → tonnes/year

    # Deterministic multiplier based on the numeric part of the facility id
    # so each facility gets a stable, varied discrepancy level
    seed = sum(ord(c) for c in str(reported_ch4_kt)) % 10
    if seed < 4:
        # CLEAR — satellite within 10% of reported
        multiplier = 1.0 + (seed * 0.02)
    elif seed < 7:
        # WATCH — satellite 20-60% above reported
        multiplier = 1.2 + (seed - 4) * 0.15
    else:
        # HIGH — satellite >80% above reported
        multiplier = 1.8 + (seed - 7) * 0.30

    estimate = base_t * multiplier
    sigma = estimate * 0.12   # ~12% relative uncertainty
    return round(estimate, 1), round(estimate - 1.96 * sigma, 1), round(estimate + 1.96 * sigma, 1)


def _evs_and_flag(estimate: float, reported_t: float | None) -> tuple[float, str]:
    """Replicate the EVS formula from ml/app/services/evs_scorer.py."""
    if reported_t is None or reported_t <= 0:
        return 50.0, "watch"

    delta_pct = ((estimate - reported_t) / reported_t) * 100.0
    sigma = estimate * 0.12 / 1.96
    sigma_dev = (estimate - reported_t) / sigma if sigma > 0 else 0.0
    evs = max(0.0, 100.0 * math.exp(-0.008 * max(0.0, delta_pct)))

    if sigma_dev > 2.0:
        flag = "high"
    elif sigma_dev > 1.0:
        flag = "watch"
    else:
        flag = "clear"

    return round(evs, 1), flag


def main() -> None:
    if not FIXTURES.exists():
        print(f"ERROR: {FIXTURES} not found.", file=sys.stderr)
        sys.exit(1)

    PROCESSED.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(FIXTURES)

    # ── facilities.parquet ────────────────────────────────────────────────────
    facilities_df = df[["facility_id", "facility_name", "latitude", "longitude", "sector"]].copy()
    facilities_path = PROCESSED / "facilities.parquet"
    facilities_df.to_parquet(facilities_path, index=False)
    print(f"Wrote {len(facilities_df)} facilities → {facilities_path}")

    # ── evs_scores.parquet ────────────────────────────────────────────────────
    rows = []
    for _, row in df.iterrows():
        reported_kt = row.get("reported_ch4_kt")
        reported_t = float(reported_kt) * 1_000.0 if pd.notna(reported_kt) and float(reported_kt) > 0 else None

        est, low, high = _satellite_estimate(reported_kt if pd.notna(reported_kt) else None)
        evs, flag = _evs_and_flag(est, reported_t)

        days_valid = TOTAL_DAYS - (sum(ord(c) for c in row["facility_id"]) % 8)  # 22–30 days

        rows.append({
            "facility_id": row["facility_id"],
            "facility_name": row["facility_name"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "observation_start": OBS_START.isoformat(),
            "observation_end": OBS_END.isoformat(),
            "days_with_valid_retrievals": days_valid,
            "coverage_pct": round(days_valid / TOTAL_DAYS * 100, 1),
            "satellite_ch4_estimate": est,
            "satellite_uncertainty_low": low,
            "satellite_uncertainty_high": high,
            "reported_ch4": reported_t,
            "reported_source": f"ESG Report {row.get('operator', '')}",
            "reported_year": 2023,
            "delta_pct": round((est - reported_t) / reported_t * 100, 2) if reported_t else None,
            "sigma_deviation": None,
            "evs": evs,
            "flag": flag,
            "blockchain_tx_id": None,
            "report_id": None,
        })

    scores_df = pd.DataFrame(rows)
    scores_path = PROCESSED / "evs_scores.parquet"
    scores_df.to_parquet(scores_path, index=False)
    print(f"Wrote {len(scores_df)} EVS scores → {scores_path}")


if __name__ == "__main__":
    main()
