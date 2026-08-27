"""
backend/app/tasks/sentinel.py
──────────────────────────────
Celery tasks for Sentinel-5P TROPOMI data ingestion.

Task hierarchy
--------------
trigger_sentinel_download
    └─ (spawns) download_sentinel_product  ×N  (one per matched product)

Queue:  downloads
Retry:  exponential back-off, max 5 attempts (network-bound)
States: PENDING → STARTED → PROGRESS → SUCCESS | FAILURE
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from celery import Task
from celery.utils.log import get_task_logger

from app.tasks.celery_app import celery_app
from app.tasks.paths import script_path

log: logging.Logger = get_task_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
_SCRIPT = script_path("download_sentinel5p.py")
_DEFAULT_OUT_DIR = "data/raw/sentinel5p"
_MAX_RETRIES = 5
_RETRY_BASE = 60  # seconds — doubled on each retry


# ── Base task class for download tasks ───────────────────────────────────────

class DownloadTask(Task):
    """
    Abstract base that sets common download-task options and
    provides a helper for structured progress updates.
    """

    abstract = True
    queue = "downloads"
    acks_late = True  # do not ack until the worker has finished
    reject_on_worker_lost = True  # re-queue if a worker crashes mid-download

    def update_progress(
        self,
        current: int,
        total: int,
        description: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        meta: dict[str, Any] = {
            "current": current,
            "total": total,
            "description": description,
        }
        if extra:
            meta.update(extra)
        self.update_state(state="PROGRESS", meta=meta)


# ── Tasks ─────────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=DownloadTask,
    name="sentinel.trigger_download",
    max_retries=_MAX_RETRIES,
    soft_time_limit=7200,   # 2 h  — warn + raise SoftTimeLimitExceeded
    time_limit=7500,        # 2 h 5 min — hard kill
)
def trigger_sentinel_download(
    self: DownloadTask,
    start_date: str,
    end_date: str,
    bbox: str,
    product_type: str = "L2__CH4___",
    out_dir: str = _DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    """
    Orchestrating task: invoke the download_sentinel5p.py script as a subprocess
    and stream its output into Celery task progress updates.

    Parameters
    ----------
    start_date   : ISO date string, e.g. "2024-01-01"
    end_date     : ISO date string, e.g. "2024-01-31"
    bbox         : Comma-separated floats "W,S,E,N"
    product_type : TROPOMI product type (default: L2__CH4___)
    out_dir      : Destination directory for downloaded files

    Returns
    -------
    dict with keys: status, out_dir, product_type, start_date, end_date
    """
    log.info(
        "Task %s — Sentinel-5P download requested: %s → %s, product=%s, bbox=%s",
        self.request.id, start_date, end_date, product_type, bbox,
    )
    self.update_progress(0, 1, f"Starting Sentinel-5P {product_type} download …")

    env = {**os.environ, "PYTHONUNBUFFERED": "1"}

    cmd = [
        sys.executable,
        str(_SCRIPT),
        "--start-date", start_date,
        "--end-date", end_date,
        "--bbox", bbox,
        "--product", product_type,
        "--out-dir", out_dir,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=7000,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        log.error("Sentinel download script timed out: %s", exc)
        raise self.retry(
            exc=exc,
            countdown=_backoff(self.request.retries),
        )
    except Exception as exc:  # noqa: BLE001
        log.error("Sentinel download script raised unexpected error: %s", exc)
        raise self.retry(
            exc=exc,
            countdown=_backoff(self.request.retries),
        )

    if result.stdout:
        for line in result.stdout.strip().splitlines():
            log.info("[script stdout] %s", line)
    if result.stderr:
        for line in result.stderr.strip().splitlines():
            log.warning("[script stderr] %s", line)

    if result.returncode != 0:
        err_msg = (
            f"download_sentinel5p.py exited with code {result.returncode}. "
            f"Tail stderr: {result.stderr[-500:]}"
        )
        log.error(err_msg)
        raise self.retry(
            exc=RuntimeError(err_msg),
            countdown=_backoff(self.request.retries),
        )

    self.update_progress(1, 1, "Download complete.")
    log.info("Task %s — Sentinel-5P download finished successfully.", self.request.id)

    return {
        "status": "success",
        "out_dir": out_dir,
        "product_type": product_type,
        "start_date": start_date,
        "end_date": end_date,
    }


@celery_app.task(
    bind=True,
    base=DownloadTask,
    name="sentinel.download_product",
    max_retries=_MAX_RETRIES,
    soft_time_limit=3600,
    time_limit=3700,
)
def download_sentinel_product(
    self: DownloadTask,
    product_name: str,
    product_id: str,
    out_dir: str = _DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    """
    Download a single pre-resolved Sentinel-5P product by its CDSE product ID.

    This task is intended to be called by an orchestrator (e.g., a Celery group
    or chord) when individual product-level parallelism is desired.

    Parameters
    ----------
    product_name : Human-readable product filename (used for output path).
    product_id   : CDSE OData product UUID.
    out_dir      : Destination directory.

    Returns
    -------
    dict with keys: status, path, product_id
    """
    import requests  # type: ignore[import]

    log.info(
        "Task %s — Downloading single product %s (id=%s)",
        self.request.id, product_name, product_id,
    )
    self.update_progress(0, 1, f"Fetching product {product_name} …")

    username = os.environ.get("COPERNICUS_USERNAME", "")
    password = os.environ.get("COPERNICUS_PASSWORD", "")
    client_id = os.environ.get("COPERNICUS_CLIENT_ID", "cdse-public")

    if not username or not password:
        raise ValueError(
            "COPERNICUS_USERNAME and COPERNICUS_PASSWORD must be set in the environment."
        )

    # Obtain a fresh token for this task invocation
    token_url = (
        "https://identity.dataspace.copernicus.eu"
        "/auth/realms/CDSE/protocol/openid-connect/token"
    )
    try:
        tok_resp = requests.post(
            token_url,
            data={
                "grant_type": "password",
                "username": username,
                "password": password,
                "client_id": client_id,
            },
            timeout=30,
        )
        tok_resp.raise_for_status()
        access_token: str = tok_resp.json()["access_token"]
    except requests.RequestException as exc:
        raise self.retry(exc=exc, countdown=_backoff(self.request.retries))

    out_path = Path(out_dir) / product_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    download_url = (
        f"https://download.dataspace.copernicus.eu"
        f"/odata/v1/Products({product_id})/$value"
    )

    existing_bytes = out_path.stat().st_size if out_path.exists() else 0
    headers: dict[str, str] = {"Authorization": f"Bearer {access_token}"}
    if existing_bytes:
        headers["Range"] = f"bytes={existing_bytes}-"

    try:
        with requests.get(download_url, headers=headers, stream=True, timeout=120) as resp:
            if resp.status_code == 416:
                log.info("Product %s already complete.", product_name)
                return {"status": "skipped", "path": str(out_path), "product_id": product_id}
            resp.raise_for_status()
            mode = "ab" if existing_bytes and resp.status_code == 206 else "wb"
            with open(out_path, mode) as fh:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    if chunk:
                        fh.write(chunk)
    except requests.RequestException as exc:
        raise self.retry(exc=exc, countdown=_backoff(self.request.retries))

    self.update_progress(1, 1, f"Saved {product_name}.")
    log.info("Task %s — Product saved: %s", self.request.id, out_path)
    return {"status": "success", "path": str(out_path), "product_id": product_id}


# ── Utilities ─────────────────────────────────────────────────────────────────

def _backoff(retries: int, base: int = _RETRY_BASE) -> int:
    """Exponential back-off with a cap of 1 hour."""
    return min(base * (2**retries), 3600)
