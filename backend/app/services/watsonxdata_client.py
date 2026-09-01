"""
backend/app/services/watsonxdata_client.py
──────────────────────────────────────────
IBM watsonx.data (Presto) client for federated facility registry queries.

E-4: Competitive Edge — connects the facility registry query to IBM watsonx.data
instead of a flat Parquet file when WATSONXDATA_HOST is configured.

IBM watsonx.data exposes a Presto-compatible JDBC/HTTP endpoint.  This client
uses the prestodb Python driver (via httpx for the REST path) to issue SQL
queries against the watsonx.data Presto engine.

ADR-002 extension: When WATSONXDATA_HOST is present, facility registry reads are
routed through watsonx.data rather than the local Parquet file.  The data itself
is unchanged — the query path demonstrates IBM platform breadth.

Fallback: if watsonx.data is not configured, falls back to the Parquet store
transparently.  No existing code paths are broken.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Presto REST API paths
_QUERY_PATH = "/v1/statement"
_NEXT_URI_HEADER = "nextUri"


class WatsonxDataClient:
    """
    Minimal Presto REST client for IBM watsonx.data.

    Executes a single SQL statement and returns rows as a list of dicts.
    Uses the Presto HTTP API (v1/statement) which is the same protocol
    that the prestodb JDBC driver uses under the hood.

    Credentials:
        WATSONXDATA_HOST         — Presto coordinator hostname
        WATSONXDATA_PORT         — port (default 443)
        WATSONXDATA_ACCESS_TOKEN — Bearer token from IBM Cloud IAM

    Example query:
        client = WatsonxDataClient()
        rows = await client.query(
            "SELECT facility_id, facility_name, latitude, longitude, sector "
            "FROM hive.thermalledger.facilities"
        )
    """

    def __init__(self) -> None:
        self._host = settings.watsonxdata_host
        self._port = settings.watsonxdata_port
        self._token = settings.watsonxdata_access_token

    @property
    def is_configured(self) -> bool:
        """True when WATSONXDATA_HOST and WATSONXDATA_ACCESS_TOKEN are present."""
        return bool(self._host and self._token)

    def _base_url(self) -> str:
        scheme = "https" if self._port == 443 else "http"
        return f"{scheme}://{self._host}:{self._port}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "X-Presto-User": "thermalledger",
            "X-Presto-Catalog": "hive",
            "X-Presto-Schema": "thermalledger",
            "Content-Type": "text/plain",
            "Accept": "application/json",
        }

    async def query(self, sql: str) -> list[dict[str, Any]]:
        """
        Execute a Presto SQL query against watsonx.data and return rows as dicts.

        Handles multi-page result sets by following nextUri links.
        Raises RuntimeError on query failure.
        """
        if not self.is_configured:
            raise RuntimeError(
                "watsonx.data is not configured. Set WATSONXDATA_HOST and "
                "WATSONXDATA_ACCESS_TOKEN in .env."
            )

        async with httpx.AsyncClient(timeout=30, verify=True) as client:
            # Submit the query
            resp = await client.post(
                f"{self._base_url()}{_QUERY_PATH}",
                headers=self._headers(),
                content=sql,
            )
            resp.raise_for_status()
            data = resp.json()

            rows = []
            columns: list[str] = []

            while True:
                # Extract column names from first page
                if not columns and "columns" in data:
                    columns = [col["name"] for col in data["columns"]]

                # Collect rows
                if "data" in data:
                    for row in data["data"]:
                        if columns:
                            rows.append(dict(zip(columns, row)))
                        else:
                            rows.append({"row": row})

                # Check for query error
                if data.get("error"):
                    err = data["error"]
                    raise RuntimeError(
                        f"watsonx.data query error [{err.get('errorCode')}]: "
                        f"{err.get('message', 'unknown error')}"
                    )

                # Follow nextUri if present
                next_uri = data.get("nextUri")
                if not next_uri:
                    break

                resp = await client.get(next_uri, headers=self._headers())
                resp.raise_for_status()
                data = resp.json()

        return rows

    async def get_facilities(self) -> list[dict[str, Any]] | None:
        """
        Fetch the full facility registry from watsonx.data.
        Returns None on any error so callers can fall back to Parquet.

        The expected table schema matches the facility Parquet fixture:
          facility_id, facility_name, latitude, longitude, sector
        """
        sql = (
            "SELECT facility_id, facility_name, latitude, longitude, sector "
            "FROM hive.thermalledger.facilities "
            "ORDER BY facility_name"
        )
        try:
            rows = await self.query(sql)
            logger.info("watsonx.data returned %d facility rows", len(rows))
            return rows
        except Exception as exc:  # noqa: BLE001
            logger.warning("watsonx.data facility query failed: %s", exc)
            return None


# Singleton
_wxd_client: WatsonxDataClient | None = None


def get_watsonxdata_client() -> WatsonxDataClient:
    global _wxd_client
    if _wxd_client is None:
        _wxd_client = WatsonxDataClient()
    return _wxd_client


async def get_facilities_from_watsonxdata_or_parquet() -> list[dict[str, Any]] | None:
    """
    Try watsonx.data first; fall back to Parquet store if not configured or on error.

    Returns None only when the Parquet fallback also fails, which should not
    happen in normal operation (Parquet fixtures are committed to the repo).
    """
    client = get_watsonxdata_client()
    if client.is_configured:
        result = await client.get_facilities()
        if result is not None:
            return result
        logger.info("Falling back to Parquet store for facility registry.")

    # Parquet fallback
    try:
        from app.services.parquet_store import get_facility_records
        return get_facility_records()
    except Exception as exc:  # noqa: BLE001
        logger.error("Parquet fallback also failed: %s", exc)
        return None
