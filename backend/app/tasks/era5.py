"""
backend/app/tasks/era5.py
──────────────────────────
Celery tasks for ERA5 reanalysis data ingestion via the ECMWF CDS API.

Task hierarchy
--------------
trigger_era5_download
    └─ (spawns) download_era5_month  ×N  (one per calendar-month slice)

Queue:  downloads
Retry:  exponential back-off, max 5 attempts (CDS queue can be slow)
States: PENDING → STARTED → PROGRESS → SUCCESS | FAILURE

CDS jobs can spend minutes in a remote queue before delivering data;
the soft_time_limit is therefore set generously at 4 h per month-task.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from celery import Task
from celery.utils.log import get_task_logger

from app.tasks.celery_app import celery_app
from app.tasks.paths import script_path

log: logging.Logger = get_task_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
_SCRIPT = script_path("download_era5.py")
_DEFAULT_OUT_DIR = "data/raw/era5"
_MAX_RETRIES = 5
_RETRY_BASE = 90  # seconds — CDS queue waits can be long


# ── Base task ─────────────────────────────────────────────────────────────────

class DownloadTask(Task):
    abstract = True
    queue = "downloads"
    acks_late = True
    reject_on_worker_lost = True

    def update_progress(
        self,
        current: int,
        total: int,
        description: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        meta: dict[str, Any] = {"current": current, "total": total, "description": description}
        if extra:
            meta.update(extra)
        self.update_state(state="PROGRESS", meta=meta)


# ── Tasks ─────────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=DownloadTask,
    name="era5.trigger_download",
    max_retries=_MAX_RETRIES,
    soft_time_limit=14400,   # 4 h
    time_limit=14700,
)
def trigger_era5_download(
    self: DownloadTask,
    start_date: str,
    end_date: str,
    variables: str = (
        "2m_temperature,"
        "10m_u_component_of_wind,"
        "10m_v_component_of_wind,"
        "boundary_layer_height"
    ),
    bbox: str | None = None,
    output_format: str = "netcdf",
    out_dir: str = _DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    """
    Orchestrating task: invoke the download_era5.py script as a subprocess
    and report progress back to Celery.

    Parameters
    ----------
    start_date     : ISO date string, e.g. "2024-01-01"
    end_date       : ISO date string, e.g. "2024-01-31"
    variables      : Comma-separated CDS variable names
    bbox           : Bounding box "W,S,E,N" (optional, None = global)
    output_format  : "netcdf" or "grib"
    out_dir        : Destination directory for downloaded files

    Returns
    -------
    dict with keys: status, out_dir, variables, start_date, end_date, format
    """
    log.info(
        "Task %s — ERA5 download requested: %s → %s, vars=%s",
        self.request.id, start_date, end_date, variables,
    )
    self.update_progress(0, 1, f"Starting ERA5 download {start_date} → {end_date} …")

    env = {**os.environ, "PYTHONUNBUFFERED": "1"}

    cmd = [
        sys.executable,
        str(_SCRIPT),
        "--start-date", start_date,
        "--end-date", end_date,
        "--variables", variables,
        "--format", output_format,
        "--out-dir", out_dir,
    ]
    if bbox:
        cmd += ["--bbox", bbox]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=14000,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        log.error("ERA5 download script timed out: %s", exc)
        raise self.retry(exc=exc, countdown=_backoff(self.request.retries))
    except Exception as exc:  # noqa: BLE001
        log.error("ERA5 download script raised unexpected error: %s", exc)
        raise self.retry(exc=exc, countdown=_backoff(self.request.retries))

    if result.stdout:
        for line in result.stdout.strip().splitlines():
            log.info("[script stdout] %s", line)
    if result.stderr:
        for line in result.stderr.strip().splitlines():
            log.warning("[script stderr] %s", line)

    if result.returncode != 0:
        err_msg = (
            f"download_era5.py exited with code {result.returncode}. "
            f"Tail stderr: {result.stderr[-500:]}"
        )
        log.error(err_msg)
        raise self.retry(
            exc=RuntimeError(err_msg),
            countdown=_backoff(self.request.retries),
        )

    self.update_progress(1, 1, "ERA5 download complete.")
    log.info("Task %s — ERA5 download finished successfully.", self.request.id)

    return {
        "status": "success",
        "out_dir": out_dir,
        "variables": variables,
        "start_date": start_date,
        "end_date": end_date,
        "format": output_format,
    }


@celery_app.task(
    bind=True,
    base=DownloadTask,
    name="era5.download_month",
    max_retries=_MAX_RETRIES,
    soft_time_limit=14400,
    time_limit=14700,
)
def download_era5_month(
    self: DownloadTask,
    year: str,
    month: str,
    days: list[str],
    variables: list[str],
    area: list[float] | None,
    output_format: str,
    out_dir: str = _DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    """
    Download a single calendar-month slice of ERA5 data via the CDS API.

    Designed to be dispatched as part of a Celery group when fine-grained
    parallelism over months is required.

    Parameters
    ----------
    year          : Four-digit year string, e.g. "2024"
    month         : Zero-padded month string, e.g. "01"
    days          : List of zero-padded day strings, e.g. ["01","02",…]
    variables     : CDS variable name list
    area          : [north, west, south, east] or None for global
    output_format : "netcdf" or "grib"
    out_dir       : Destination directory

    Returns
    -------
    dict with keys: status, path, year, month
    """
    try:
        import cdsapi  # type: ignore[import]
    except ImportError:
        raise RuntimeError(
            "cdsapi is not installed. Add it to backend/pyproject.toml dependencies."
        )

    api_url = os.environ.get("CDS_API_URL", "https://cds.climate.copernicus.eu/api/v2")
    api_key = os.environ.get("CDS_API_KEY", "")
    if not api_key:
        raise ValueError("CDS_API_KEY must be set in the environment.")

    log.info(
        "Task %s — ERA5 month %s-%s: %d day(s), %d variable(s)",
        self.request.id, year, month, len(days), len(variables),
    )
    self.update_progress(0, 1, f"Requesting ERA5 {year}-{month} from CDS …")

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    ext = "nc" if output_format == "netcdf" else "grib"
    safe_vars = "-".join(v.replace("_", "")[:8] for v in variables[:3])
    filename = out_path / f"era5_{year}{month}_{safe_vars}.{ext}"

    if filename.exists():
        log.info("File already exists, skipping: %s", filename)
        return {"status": "skipped", "path": str(filename), "year": year, "month": month}

    request: dict[str, Any] = {
        "product_type": "reanalysis",
        "variable": variables,
        "year": year,
        "month": month,
        "day": days,
        "time": [f"{h:02d}:00" for h in range(24)],
        "format": output_format,
    }
    if area:
        request["area"] = area

    client = cdsapi.Client(url=api_url, key=api_key, quiet=True)

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            log.info("CDS retrieve attempt %d/%d …", attempt, _MAX_RETRIES)
            client.retrieve("reanalysis-era5-single-levels", request, str(filename))
            break
        except Exception as exc:  # noqa: BLE001
            wait = _backoff(attempt - 1)
            log.warning(
                "CDS retrieve attempt %d/%d failed: %s. Retrying in %d s …",
                attempt, _MAX_RETRIES, exc, wait,
            )
            if attempt == _MAX_RETRIES:
                raise self.retry(exc=exc, countdown=_backoff(self.request.retries))
            time.sleep(wait)

    self.update_progress(1, 1, f"Saved ERA5 {year}-{month}.")
    log.info("Task %s — Saved: %s", self.request.id, filename)
    return {"status": "success", "path": str(filename), "year": year, "month": month}


# ── Utilities ─────────────────────────────────────────────────────────────────

def _backoff(retries: int, base: int = _RETRY_BASE) -> int:
    """Exponential back-off capped at 2 h."""
    return min(base * (2**retries), 7200)
