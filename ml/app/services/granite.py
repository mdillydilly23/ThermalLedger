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


    # ── EVS explanation ───────────────────────────────────────

    async def explain_evs_score(self, evs_data: dict, question: str) -> dict[str, Any]:
        """
        Answer a user's question about a facility's EVS score using Granite.
        Returns: dict with answer (str) and cached (bool).
        """
        if self._mode == "cached":
            return self._cached_explain(evs_data, question)
        return await self._live_explain(evs_data, question)

    def _cached_explain(self, evs_data: dict, question: str) -> dict[str, Any]:
        """Return a deterministic explanation built directly from EVS data — no API call."""
        flag = str(evs_data.get("flag") or "").lower()
        flag_label = {
            "high": "HIGH — significant discrepancy",
            "watch": "WATCH — possible under-reporting",
            "clear": "CLEAR — within tolerance",
        }.get(flag, flag.upper())
        facility_name = str(evs_data.get("facility_name") or evs_data.get("facility_id") or "this facility")
        evs_score = evs_data.get("evs")
        evs_display = f"{float(evs_score):.1f}" if evs_score is not None else "unknown"
        sat_ch4 = evs_data.get("satellite_ch4_estimate")
        sat_display = f"{float(sat_ch4):,.0f} t/yr" if sat_ch4 is not None else "not available"
        reported_ch4 = evs_data.get("reported_ch4")
        reported_display = f"{float(reported_ch4):,.0f} t/yr" if reported_ch4 is not None else "not disclosed"
        delta_pct = evs_data.get("delta_pct")
        delta_display = f"{float(delta_pct):+.1f}%" if delta_pct is not None else "unavailable"
        sigma = evs_data.get("sigma_deviation")
        sigma_display = f"{float(sigma):.2f}σ" if sigma is not None else "unavailable"
        coverage = evs_data.get("coverage_pct")
        coverage_display = f"{float(coverage):.1f}%" if coverage is not None else "unavailable"
        obs_start = str(evs_data.get("observation_start") or "unknown")
        obs_end = str(evs_data.get("observation_end") or "unknown")

        answer = (
            f"**{facility_name}** received an EVS of **{evs_display}** with a flag of **{flag_label}**.\n\n"
            f"During the observation window ({obs_start} to {obs_end}), Sentinel-5P TROPOMI estimated "
            f"methane emissions at **{sat_display}**, while the facility's own Scope 1 disclosure was "
            f"**{reported_display}**. That corresponds to a discrepancy of **{delta_display}** "
            f"({sigma_display} from the satellite uncertainty interval) and a satellite data coverage "
            f"of **{coverage_display}**.\n\n"
        )

        if flag == "high":
            answer += (
                "The HIGH flag means the satellite estimate exceeds the reported value by more than 2 standard "
                "deviations, which is the threshold that would normally trigger an OpenPages GRC workflow for "
                "further investigation. Common causes include fugitive emissions not captured in routine "
                "measurement protocols, tank-venting events, or under-counting of secondary emission sources."
            )
        elif flag == "watch":
            answer += (
                "The WATCH flag means the satellite estimate is between 1 and 2 standard deviations above the "
                "reported value. This warrants monitoring but does not by itself indicate deliberate misreporting. "
                "Measurement methodology differences, temporal sampling gaps, and plume attribution uncertainty "
                "can all contribute to a WATCH-level reading."
            )
        else:
            answer += (
                "The CLEAR flag indicates that the satellite estimate is consistent with the reported value within "
                "the 95% confidence interval of the TROPOMI retrieval. No significant discrepancy was detected "
                "for this observation window."
            )

        answer += (
            "\n\n*This explanation is a demonstration prototype generated from pre-computed EVS fixture data. "
            "It is not a live satellite retrieval or a legal attestation.*"
        )

        return {"answer": answer, "cached": True}

    async def _live_explain(self, evs_data: dict, question: str) -> dict[str, Any]:
        prompt = f"""You are ThermalLedger, a methane-emissions analyst AI. A reviewer is examining an
Emission Verification Score (EVS) for an industrial facility. Answer their question clearly and concisely
based on the evidence JSON provided. Use plain English; define any acronym on first use.
Limit your answer to 4 short paragraphs. Do not start with "I" or "As an AI".

EVS evidence:
{json.dumps(evs_data, indent=2, default=str)}

Reviewer question: {question}

Answer:"""
        answer = await self._watsonx_generate(prompt, max_new_tokens=600)
        return {"answer": answer.strip(), "cached": False}


    # ── Report generation ─────────────────────────────────────

    async def generate_verification_report(self, facility_id: str, evs_data: dict) -> dict[str, Any]:
        """
        Generate a 2-page SEC/CSRD-aligned Emission Verification Report.
        Returns: dict with report_html and report_id.
        """
        if self._mode == "cached":
            return self._load_cached_report(facility_id, evs_data)
        return await self._live_generate_report(facility_id, evs_data)

    def _load_cached_report(self, facility_id: str, evs_data: dict | None = None) -> dict[str, Any]:
        report_file = self._reports_dir / f"{facility_id}_report.html"
        # If there is no facility-specific file, render directly from EVS data
        # so every facility gets a meaningful report instead of generic boilerplate.
        if not report_file.exists() and evs_data:
            report_html = _render_evs_report(evs_data, facility_id)
        elif not report_file.exists():
            report_file = self._reports_dir / "hero_facility_report.html"
            with open(report_file) as f:
                report_html = f.read()
        else:
            with open(report_file) as f:
                report_html = f.read()
        return {
            "report_id": f"cached_{facility_id}",
            "facility_id": facility_id,
            "report_html": report_html,
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


def _render_evs_report(evs_data: dict[str, Any], facility_id: str) -> str:
    """Render a facility-specific HTML report directly from EVS data — zero extra API calls."""
    flag = str(evs_data.get("flag") or "").lower()
    flag_color = {"high": "#ef4444", "watch": "#f59e0b", "clear": "#22c55e"}.get(flag, "#888888")
    flag_label = {"high": "HIGH — Significant discrepancy", "watch": "WATCH — Possible under-reporting", "clear": "CLEAR — Within tolerance"}.get(flag, flag.upper() or "UNSCORED")
    facility_name = html.escape(str(evs_data.get("facility_name") or facility_id))
    evs_score = evs_data.get("evs")
    evs_display = f"{float(evs_score):.1f}" if evs_score is not None else "—"
    sat_ch4 = evs_data.get("satellite_ch4_estimate")
    sat_display = f"{float(sat_ch4):,.0f} t/yr" if sat_ch4 is not None else "—"
    reported_ch4 = evs_data.get("reported_ch4")
    reported_display = f"{float(reported_ch4):,.0f} t/yr" if reported_ch4 is not None else "Not disclosed"
    delta_pct = evs_data.get("delta_pct")
    delta_display = (f"{float(delta_pct):+.1f}%") if delta_pct is not None else "—"
    obs_start = html.escape(str(evs_data.get("observation_start") or "—"))
    obs_end = html.escape(str(evs_data.get("observation_end") or "—"))
    coverage = evs_data.get("coverage_pct")
    coverage_display = f"{float(coverage):.1f}%" if coverage is not None else "—"
    reported_source = html.escape(str(evs_data.get("reported_source") or "—"))
    reported_year = evs_data.get("reported_year")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>ThermalLedger Verification Report — {facility_name}</title>
  <style>
    body {{ font-family: Arial, sans-serif; color: #172033; margin: 24px; line-height: 1.45; font-size: 13px; }}
    h1 {{ color: #123c6b; font-size: 18px; margin-bottom: 2px; }}
    h2 {{ font-size: 13px; margin: 18px 0 6px; color: #285f91; text-transform: uppercase; letter-spacing: 0.04em; }}
    .evs {{ display: inline-block; font-size: 28px; font-weight: 800; color: {flag_color}; }}
    .flag {{ display: inline-block; background: {flag_color}22; color: {flag_color}; border-radius: 12px; padding: 3px 10px; font-size: 11px; font-weight: bold; margin-left: 10px; vertical-align: middle; }}
    table {{ border-collapse: collapse; width: 100%; }}
    td {{ padding: 5px 8px; border-bottom: 1px solid #e5e7eb; font-size: 12px; }}
    td:first-child {{ color: #6b7280; width: 45%; }}
    .note {{ background: #edf5ff; border-left: 3px solid #3b82f6; padding: 9px; font-size: 11px; color: #374151; margin-top: 18px; }}
  </style>
</head>
<body>
  <h1>{facility_name}</h1>
  <p style="color:#6b7280;font-size:11px;margin:2px 0 16px">Facility ID: {html.escape(facility_id)}</p>

  <h2>Emission Verification Score</h2>
  <div><span class="evs">{evs_display}</span><span class="flag">{flag_label}</span></div>

  <h2>Observation Window</h2>
  <table>
    <tr><td>Start</td><td>{obs_start}</td></tr>
    <tr><td>End</td><td>{obs_end}</td></tr>
    <tr><td>Coverage</td><td>{coverage_display}</td></tr>
  </table>

  <h2>Satellite Estimate vs. Reported</h2>
  <table>
    <tr><td>Satellite CH₄ estimate</td><td><strong>{sat_display}</strong></td></tr>
    <tr><td>Reported CH₄ (Scope 1)</td><td>{reported_display}</td></tr>
    <tr><td>Discrepancy (delta)</td><td style="color:{flag_color};font-weight:600">{delta_display}</td></tr>
    <tr><td>Reported source</td><td>{reported_source}</td></tr>
    <tr><td>Reporting year</td><td>{html.escape(str(reported_year)) if reported_year else "—"}</td></tr>
  </table>

  <p class="note">Demonstration prototype — this report is generated from pre-computed EVS fixture data and is not a live satellite retrieval or a legal attestation.</p>
</body>
</html>"""
