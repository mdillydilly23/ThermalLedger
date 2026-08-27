"""Live verification pipeline task."""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import httpx

from app.core.celery_app import celery_app
from app.core.config import settings
from app.services.audit import anchor_payload, audit_mode, create_case, record_run
from app.services.parquet_store import (
    get_evs_score,
    get_facility_records,
    upsert_evs_scores,
    write_processed_plume,
)
from app.tasks.paths import script_path


@celery_app.task(bind=True, name="app.tasks.verification.run_verification")
def run_verification(
    self,
    start_date: str,
    end_date: str,
    facility_ids: list[str] | None = None,
    bbox: list[float] | None = None,
    reuse_existing_raw_data: bool = True,
) -> dict[str, Any]:
    """Run Sentinel/ERA5 attribution and persist updated EVS scores."""
    run_id = uuid4().hex
    started_at = _utc_now()
    facilities = get_facility_records(facility_ids)
    if not facilities:
        raise ValueError("No matching facilities were found for this verification run.")

    observation_start = _parse_date(start_date)
    observation_end = _parse_date(end_date)
    if observation_start > observation_end:
        raise ValueError("start_date must not be after end_date.")

    run_summary = {
        "run_id": run_id,
        "task_id": self.request.id,
        "status": "started",
        "started_at": started_at,
        "facility_count": len(facilities),
        "observation_start": start_date,
        "observation_end": end_date,
        "source": "sentinel5p_live_attribution",
    }
    record_run(run_summary)

    try:
        selected_bbox = bbox if bbox is not None else _bbox_for_facilities(facilities)
        if not reuse_existing_raw_data:
            self.update_state(state="PROGRESS", meta={"stage": "Downloading Sentinel-5P CH4 products..."})
            _run_download(
                "download_sentinel5p.py",
                [
                    "--start-date", start_date,
                    "--end-date", end_date,
                    f"--bbox={_format_bbox(selected_bbox)}",
                    "--product", "L2__CH4___",
                    "--out-dir", str(settings.data_dir / "raw" / "sentinel5p"),
                ],
            )
            self.update_state(state="PROGRESS", meta={"stage": "Downloading ERA5 wind fields..."})
            _run_download(
                "download_era5.py",
                [
                    "--start-date", start_date,
                    "--end-date", end_date,
                    "--variables", "10m_u_component_of_wind,10m_v_component_of_wind,boundary_layer_height",
                    f"--bbox={_format_bbox(selected_bbox)}",
                    "--format", "netcdf",
                    "--out-dir", str(settings.data_dir / "raw" / "era5"),
                ],
            )

        scores: list[dict[str, Any]] = []
        for index, facility in enumerate(facilities, start=1):
            stage = f"Attributing plume {index}/{len(facilities)}: {facility['facility_name']}"
            self.update_state(state="PROGRESS", meta={"stage": stage})
            existing_score = get_evs_score(facility["facility_id"]) or {}
            payload = _attribute_facility(facility, existing_score, start_date, end_date)

            score = dict(payload["score"])
            anchor = anchor_payload("evs_score", score)
            score["blockchain_tx_id"] = anchor["anchor_id"]
            if score.get("flag") in {"watch", "high"}:
                create_case(
                    facility_id=score["facility_id"],
                    severity=str(score["flag"]),
                    payload={
                        "run_id": run_id,
                        "score": score,
                        "source": payload.get("source", "sentinel5p_live_attribution"),
                    },
                )

            write_processed_plume(
                facility_id=score["facility_id"],
                observation_date=end_date,
                geojson=payload["geojson"],
                source=payload.get("source", "sentinel5p_live_attribution"),
            )
            scores.append(score)

        self.update_state(state="PROGRESS", meta={"stage": "Persisting EVS scores..."})
        upserted = upsert_evs_scores(scores)
        completed = {
            **run_summary,
            "status": "success",
            "completed_at": _utc_now(),
            "processed_facilities": upserted,
            "audit_mode": audit_mode(),
            "scores": scores,
        }
        record_run(completed)
        return completed
    except Exception as exc:
        failed = {
            **run_summary,
            "status": "failure",
            "completed_at": _utc_now(),
            "error": str(exc),
        }
        record_run(failed)
        raise


def _attribute_facility(
    facility: dict[str, Any],
    existing_score: dict[str, Any],
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    request = {
        "facility_id": facility["facility_id"],
        "facility_name": facility["facility_name"],
        "latitude": facility["latitude"],
        "longitude": facility["longitude"],
        "start": start_date,
        "end": end_date,
        "reported_ch4": existing_score.get("reported_ch4"),
        "reported_source": existing_score.get("reported_source"),
        "reported_year": existing_score.get("reported_year"),
    }
    response = httpx.post(
        f"{settings.ml_service_url.rstrip('/')}/plume/attribute",
        json=request,
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


def _run_download(script_name: str, args: list[str]) -> None:
    script = script_path(script_name)
    result = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=14_400,
    )
    if result.returncode != 0:
        stderr = result.stderr[-1000:] if result.stderr else ""
        stdout = result.stdout[-1000:] if result.stdout else ""
        raise RuntimeError(f"{script_name} failed with code {result.returncode}: {stderr or stdout}")


def _bbox_for_facilities(facilities: list[dict[str, Any]], padding: float = 0.4) -> list[float]:
    longitudes = [float(facility["longitude"]) for facility in facilities]
    latitudes = [float(facility["latitude"]) for facility in facilities]
    return [
        min(longitudes) - padding,
        min(latitudes) - padding,
        max(longitudes) + padding,
        max(latitudes) + padding,
    ]


def _format_bbox(bbox: list[float]) -> str:
    if len(bbox) != 4:
        raise ValueError("bbox must contain [west, south, east, north].")
    return ",".join(str(value) for value in bbox)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
