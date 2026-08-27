"""
ADR-006: GraniteClient — single point of control for all watsonx.ai calls.

GRANITE_MODE=cached  → serve pre-generated outputs from ml/cache/granite/
GRANITE_MODE=live    → call watsonx.ai in real time (development only)

No route or task calls the watsonx SDK directly — always goes through this class.
"""

import asyncio
import html
import json
import re
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
        text = _extract_pdf_text(Path(pdf_path))
        prompt = f"""
Extract methane-related Scope 1 emissions claims from this ESG report text.
Return only valid JSON with this exact shape:
{{
  "claims": [
    {{
      "company_name": "string",
      "reporting_year": 2023,
      "scope1_ch4_tonnes": 123.4,
      "scope1_co2e_tonnes": 123.4,
      "measurement_methodology": "string or null",
      "third_party_verified": false,
      "source_page": 1
    }}
  ]
}}
Use null when a numeric value is not disclosed. Do not include commentary.

ESG report text:
{text[:14000]}
"""
        generated = await self._watsonx_generate(prompt, max_new_tokens=1000)
        parsed = _extract_json_object(generated)
        claims = [_coerce_claim(claim) for claim in parsed.get("claims", [])]
        return {
            "filename": filename,
            "claims": claims,
            "granite_model_id": settings.granite_model_id,
            "cached": False,
        }

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
            "facility_id": facility_id,
            "report_html": html,
            "cached": True,
            "blockchain_tx_id": None,  # anchored separately by backend
        }

    async def _live_generate_report(self, facility_id: str, evs_data: dict) -> dict[str, Any]:
        prompt = f"""
Write a concise analyst verification report as standalone HTML for this methane
emissions evidence. Include: facility identity, observation window, satellite
estimate, reported value, EVS score, discrepancy flag, uncertainty, and a clear
prototype limitation note. Return only HTML, no markdown fence.

Evidence JSON:
{json.dumps(evs_data, indent=2, default=str)}
"""
        generated = await self._watsonx_generate(prompt, max_new_tokens=1400)
        return {
            "report_id": f"live_{facility_id}",
            "facility_id": facility_id,
            "report_html": _normalise_report_html(generated, facility_id, evs_data),
            "cached": False,
            "blockchain_tx_id": None,
        }

    async def _watsonx_generate(self, prompt: str, max_new_tokens: int) -> str:
        if not settings.watsonx_api_key or not settings.watsonx_project_id:
            raise RuntimeError(
                "WATSONX_API_KEY and WATSONX_PROJECT_ID are required for GRANITE_MODE=live."
            )

        def _generate() -> str:
            try:
                from ibm_watsonx_ai import Credentials
                from ibm_watsonx_ai.foundation_models import ModelInference
                from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
            except ImportError as exc:
                raise RuntimeError("ibm-watsonx-ai is required for live Granite mode.") from exc

            params = {
                GenParams.DECODING_METHOD: "greedy",
                GenParams.MAX_NEW_TOKENS: max_new_tokens,
                GenParams.MIN_NEW_TOKENS: 1,
            }
            model = ModelInference(
                model_id=settings.granite_model_id,
                params=params,
                credentials=Credentials(
                    api_key=settings.watsonx_api_key,
                    url=settings.watsonx_url,
                ),
                project_id=settings.watsonx_project_id,
            )
            response = model.generate(prompt=prompt)
            return response["results"][0]["generated_text"]

        return await asyncio.to_thread(_generate)


def _extract_pdf_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    try:
        from pypdf import PdfReader
    except ImportError:
        return path.read_bytes().decode("utf-8", errors="ignore")

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    text = "\n\n".join(pages).strip()
    if not text:
        text = path.read_bytes().decode("utf-8", errors="ignore")
    return text


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.IGNORECASE | re.MULTILINE)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Granite did not return a JSON object.")
    parsed = json.loads(cleaned[start : end + 1])
    if isinstance(parsed, list):
        return {"claims": parsed}
    if not isinstance(parsed, dict):
        raise TypeError("Granite JSON response must be an object.")
    parsed.setdefault("claims", [])
    return parsed


def _coerce_claim(claim: dict[str, Any]) -> dict[str, Any]:
    return {
        "company_name": str(claim.get("company_name") or "Unknown company"),
        "reporting_year": _coerce_int(claim.get("reporting_year")) or 0,
        "scope1_ch4_tonnes": _coerce_float(claim.get("scope1_ch4_tonnes")),
        "scope1_co2e_tonnes": _coerce_float(claim.get("scope1_co2e_tonnes")),
        "measurement_methodology": claim.get("measurement_methodology"),
        "third_party_verified": bool(claim.get("third_party_verified", False)),
        "source_page": _coerce_int(claim.get("source_page")),
    }


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:,\d{3})*(?:\.\d+)?", str(value))
    return float(match.group(0).replace(",", "")) if match else None


def _coerce_int(value: Any) -> int | None:
    number = _coerce_float(value)
    return int(number) if number is not None else None


def _normalise_report_html(generated: str, facility_id: str, evs_data: dict[str, Any]) -> str:
    content = generated.strip()
    content = re.sub(r"^```(?:html)?|```$", "", content, flags=re.IGNORECASE | re.MULTILINE).strip()
    if "<html" in content.lower() or "<section" in content.lower() or "<article" in content.lower():
        return content

    facility_name = html.escape(str(evs_data.get("facility_name") or facility_id))
    body = html.escape(content).replace("\n", "<br>")
    return f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>ThermalLedger Verification Report - {facility_name}</title>
    <style>
      body {{ font-family: Inter, Arial, sans-serif; margin: 32px; color: #111827; line-height: 1.55; }}
      h1 {{ margin-bottom: 4px; }}
      .note {{ color: #6b7280; font-size: 13px; }}
    </style>
  </head>
  <body>
    <h1>{facility_name}</h1>
    <p class="note">Live Granite-generated prototype verification report.</p>
    <p>{body}</p>
  </body>
</html>
"""
