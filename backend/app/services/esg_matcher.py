"""Match extracted ESG methane claims to known facilities."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.core.config import settings
from app.services.parquet_store import get_all_evs_scores


def match_claims_to_facilities(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return best-effort facility matches for extracted ESG claims."""
    if not claims:
        return []

    candidates = _load_candidates()
    if not candidates:
        return []

    matches: list[dict[str, Any]] = []
    for claim in claims:
        candidate, reason = _best_match(claim, candidates)
        if candidate is None:
            continue
        matches.append({
            "facility_id": candidate["facility_id"],
            "facility_name": candidate["facility_name"],
            "claim_year": claim.get("reporting_year"),
            "reported_ch4": claim.get("scope1_ch4_tonnes"),
            "latest_evs": candidate.get("evs"),
            "latest_flag": candidate.get("flag"),
            "match_reason": reason,
        })
    return matches


def _load_candidates() -> list[dict[str, Any]]:
    registry_path = settings.data_dir / "fixtures" / "registry.csv"
    if registry_path.exists():
        registry = pd.read_csv(registry_path)
    else:
        registry = pd.DataFrame()

    scores = pd.DataFrame(get_all_evs_scores())
    if scores.empty:
        return []

    if registry.empty:
        frame = scores
    else:
        keep = [col for col in ["facility_id", "operator", "sector"] if col in registry.columns]
        frame = scores.merge(registry[keep], on="facility_id", how="left")

    return [_clean(record) for record in frame.to_dict(orient="records")]


def _best_match(
    claim: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    company = _normalize(str(claim.get("company_name") or ""))
    if company:
        for candidate in candidates:
            names = [
                _normalize(str(candidate.get("operator") or "")),
                _normalize(str(candidate.get("facility_name") or "")),
            ]
            if any(company in name or name in company for name in names if name):
                return candidate, "company_or_operator_name"

    claim_ch4 = claim.get("scope1_ch4_tonnes")
    if claim_ch4 is None:
        return (candidates[0], "default_first_facility") if candidates else (None, None)

    try:
        claim_value = float(claim_ch4)
    except (TypeError, ValueError):
        return (candidates[0], "default_first_facility") if candidates else (None, None)

    scored = []
    for candidate in candidates:
        reported = candidate.get("reported_ch4")
        if reported is None:
            continue
        try:
            distance = abs(float(reported) - claim_value)
        except (TypeError, ValueError):
            continue
        scored.append((distance, candidate))

    if not scored:
        return (candidates[0], "default_first_facility") if candidates else (None, None)

    scored.sort(key=lambda item: item[0])
    return scored[0][1], "closest_reported_ch4"


def _normalize(value: str) -> str:
    return "".join(char.lower() for char in value if char.isalnum())


def _clean(record: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(value, (list, tuple, dict)):
            cleaned[key] = value
            continue
        cleaned[key] = None if pd.isna(value) else value
    return cleaned
