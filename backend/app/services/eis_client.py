"""
backend/app/services/eis_client.py
────────────────────────────────────
IBM Environmental Intelligence Suite (EIS) client.

E-3: Competitive Edge — adds EIS as a third satellite data source alongside
Sentinel-5P (direct download) and ERA5 wind fields.

IBM EIS exposes a geospatial REST API at:
  https://api.ibm.com/geospatial/run/na/core/v3

Supported capability (MVP):
  • get_methane_observations() — query TROPOMI CH4 column data for a bounding
    box and time range via the EIS geospatial analytics endpoint.

ADR-002: When EIS_API_KEY is configured, EISDataProvider is offered as an
optional third provider.  The existing local/remote toggle is not changed —
EIS is additive.  In the demo, EIS returns None gracefully if the key is absent.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class EISDataProvider:
    """
    Thin wrapper around the IBM EIS Geospatial API.

    Usage:
        provider = EISDataProvider()
        data = await provider.get_methane_observations(
            facility_id="EU-ETS-DE-001",
            lat=51.5, lon=12.3,
            start=date(2024, 6, 1), end=date(2024, 6, 30),
        )

    Returns None — not an error — when EIS_API_KEY is not configured, so
    callers can treat EIS as an optional enrichment rather than a hard dependency.
    """

    BASE_URL = "https://api.ibm.com/geospatial/run/na/core/v3"

    def __init__(self) -> None:
        self._api_key = settings.eis_api_key
        self._base_url = settings.eis_base_url.rstrip("/")

    @property
    def is_configured(self) -> bool:
        """True when an EIS API key is present."""
        return bool(self._api_key)

    async def get_methane_observations(
        self,
        facility_id: str,
        lat: float,
        lon: float,
        start: date,
        end: date,
        radius_km: float = 25.0,
    ) -> dict[str, Any] | None:
        """
        Query EIS for TROPOMI methane column observations near a facility.

        Returns a dict with keys:
          facility_id, source, start, end, observations (list of data points)

        Returns None if EIS is not configured or the request fails.
        """
        if not self.is_configured:
            logger.debug("EIS_API_KEY not set — skipping EIS methane query for %s", facility_id)
            return None

        # Construct bounding box from facility centre + radius
        deg_offset = radius_km / 111.0  # ~111 km per degree lat
        bbox = {
            "west": lon - deg_offset,
            "south": lat - deg_offset,
            "east": lon + deg_offset,
            "north": lat + deg_offset,
        }

        headers = {
            "X-IBM-Client-Id": self._api_key,
            "Accept": "application/json",
        }
        params = {
            "bbox": f"{bbox['west']:.4f},{bbox['south']:.4f},{bbox['east']:.4f},{bbox['north']:.4f}",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "dataset": "tropomi_ch4",
            "aggregation": "daily_mean",
        }

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"{self._base_url}/methane/observations",
                    headers=headers,
                    params=params,
                )
            response.raise_for_status()
            raw = response.json()
            return _normalise_eis_response(facility_id, raw, start, end)
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "EIS API returned %s for facility %s: %s",
                exc.response.status_code,
                facility_id,
                exc.response.text[:200],
            )
            return None
        except httpx.HTTPError as exc:
            logger.warning("EIS API network error for facility %s: %s", facility_id, exc)
            return None

    async def get_facility_air_quality(
        self,
        facility_id: str,
        lat: float,
        lon: float,
        start: date,
        end: date,
    ) -> dict[str, Any] | None:
        """
        Query EIS for air quality index near a facility (NO2, PM2.5, O3).
        Useful for contextualising industrial emission events.

        Returns None if EIS is not configured or the request fails.
        """
        if not self.is_configured:
            return None

        headers = {"X-IBM-Client-Id": self._api_key, "Accept": "application/json"}
        params = {
            "lat": lat,
            "lon": lon,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"{self._base_url}/air-quality/history",
                    headers=headers,
                    params=params,
                )
            response.raise_for_status()
            return {"facility_id": facility_id, "source": "ibm_eis", "data": response.json()}
        except httpx.HTTPError as exc:
            logger.warning("EIS air quality query failed for %s: %s", facility_id, exc)
            return None


def _normalise_eis_response(
    facility_id: str,
    raw: dict[str, Any],
    start: date,
    end: date,
) -> dict[str, Any]:
    """Normalise the raw EIS JSON into ThermalLedger's internal format."""
    observations = raw.get("features") or raw.get("observations") or raw.get("data") or []
    return {
        "facility_id": facility_id,
        "source": "ibm_eis",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "observations": observations,
        "raw_response": raw,
    }


# Singleton — one client per backend process
_eis_client: EISDataProvider | None = None


def get_eis_client() -> EISDataProvider:
    global _eis_client
    if _eis_client is None:
        _eis_client = EISDataProvider()
    return _eis_client
