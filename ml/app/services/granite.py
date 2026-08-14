"""
ADR-006: GraniteClient — single point of control for all watsonx.ai calls.

GRANITE_MODE=cached  → serve pre-generated outputs from ml/cache/granite/
GRANITE_MODE=live    → call watsonx.ai in real time (development only)

No route or task calls the watsonx SDK directly — always goes through this class.
"""

import json
from pathlib import Path
from typing import Any

from app.core.config import settings


class GraniteClient:

    def __init__(self):
        self._mode = settings.granite_mode
        self._cache_dir = settings.granite_cache_dir
        self._reports_dir = settings.reports_cache_dir

    # ── ESG parsing ───────────────────────────────────────────

    async def parse_esg_pdf(self, pdf_path: str, filename: str) -> dict[str, Any]:
        """
        Extract structured emission claims from an ESG PDF.
        Returns: dict matching ESGParseResult schema (ADR-003).
        """
        if self._mode == "cached":
            return self._load_cached_parse(filename)
        return await self._live_parse_esg(pdf_path, filename)

    def _load_cached_parse(self, filename: str) -> dict[str, Any]:
        # Strip extension to find cache file
        stem = Path(filename).stem
        cache_file = self._cache_dir / f"{stem}.json"
        if not cache_file.exists():
            # Fall back to a generic demo result rather than crashing
            cache_file = self._cache_dir / "_demo_fallback.json"
        with open(cache_file) as f:
            result = json.load(f)
        result["cached"] = True
        return result

    async def _live_parse_esg(self, pdf_path: str, filename: str) -> dict[str, Any]:
        # TODO: implement watsonx.ai Granite PDF extraction
        # 1. Read PDF bytes
        # 2. Build structured extraction prompt with GHG Protocol taxonomy schema
        # 3. Call ibm_watsonx_ai.foundation_models.ModelInference
        # 4. Parse JSON response into ESGParseResult shape
        raise NotImplementedError("Live Granite ESG parsing not yet implemented")

    # ── Report generation ─────────────────────────────────────

    async def generate_verification_report(self, facility_id: str, evs_data: dict) -> dict[str, Any]:
        """
        Generate a 2-page SEC/CSRD-aligned Emission Verification Report.
        Returns: dict with report_html and report_id.
        """
        if self._mode == "cached":
            return self._load_cached_report(facility_id)
        return await self._live_generate_report(facility_id, evs_data)

    def _load_cached_report(self, facility_id: str) -> dict[str, Any]:
        report_file = self._reports_dir / f"{facility_id}_report.html"
        if not report_file.exists():
            report_file = self._reports_dir / "hero_facility_report.html"
        with open(report_file) as f:
            html = f.read()
        return {
            "report_id": f"cached_{facility_id}",
            "report_html": html,
            "cached": True,
            "blockchain_tx_id": None,  # anchored separately by backend
        }

    async def _live_generate_report(self, facility_id: str, evs_data: dict) -> dict[str, Any]:
        # TODO: implement Granite report generation prompt
        raise NotImplementedError("Live Granite report generation not yet implemented")
