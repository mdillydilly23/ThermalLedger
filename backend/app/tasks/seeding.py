"""
backend/app/tasks/seeding.py
──────────────────────────────
Celery tasks for facility registry seeding.

Task hierarchy
--------------
seed_facilities
    └─ invokes seed_facilities.py as a subprocess (keeps DB connection
       management inside the script and avoids importing SQLAlchemy into
       every Celery worker process)

Queue:  seeding
Retry:  up to 3 attempts with moderate back-off (DB errors are usually transient)
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
_SCRIPT = script_path("seed_facilities.py")
_DEFAULT_SOURCE = "data/fixtures/registry.csv"
_MAX_RETRIES = 3
_RETRY_BASE = 30  # seconds


# ── Base task ─────────────────────────────────────────────────────────────────

class SeedingTask(Task):
    """Base task for DB-bound seeding work — dedicated queue, lower time limits."""

    abstract = True
    queue = "seeding"
    acks_late = True

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
    base=SeedingTask,
    name="seeding.seed_facilities",
    max_retries=_MAX_RETRIES,
    soft_time_limit=600,    # 10 min — seeding should be fast
    time_limit=660,
)
def seed_facilities(
    self: SeedingTask,
    source: str = _DEFAULT_SOURCE,
    file_format: str = "csv",
    fail_fast: bool = False,
) -> dict[str, Any]:
    """
    Seed the facilities table from a registry source file.

    Parameters
    ----------
    source      : Path to the registry file (CSV or JSON).
    file_format : "csv" or "json".
    fail_fast   : If True, abort on first validation error.

    Returns
    -------
    dict with keys: status, source, format, returncode
    """
    log.info(
        "Task %s — Seeding facilities from %s (format=%s, fail_fast=%s)",
        self.request.id, source, file_format, fail_fast,
    )
    self.update_progress(0, 1, f"Seeding facilities from {source} …")

    source_path = Path(source)
    if not source_path.exists():
        err = f"Source file not found: {source_path}"
        log.error(err)
        # Do not retry — missing file won't fix itself without intervention
        raise FileNotFoundError(err)

    env = {**os.environ, "PYTHONUNBUFFERED": "1"}

    cmd = [
        sys.executable,
        str(_SCRIPT),
        "--source", str(source_path),
        "--format", file_format,
    ]
    if fail_fast:
        cmd.append("--fail-fast")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=550,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        log.error("seed_facilities.py timed out: %s", exc)
        raise self.retry(exc=exc, countdown=_backoff(self.request.retries))
    except Exception as exc:  # noqa: BLE001
        log.error("seed_facilities.py raised unexpected error: %s", exc)
        raise self.retry(exc=exc, countdown=_backoff(self.request.retries))

    if result.stdout:
        for line in result.stdout.strip().splitlines():
            log.info("[script stdout] %s", line)
    if result.stderr:
        for line in result.stderr.strip().splitlines():
            log.warning("[script stderr] %s", line)

    if result.returncode != 0:
        err_msg = (
            f"seed_facilities.py exited with code {result.returncode}. "
            f"Tail stderr: {result.stderr[-400:]}"
        )
        log.error(err_msg)
        raise self.retry(
            exc=RuntimeError(err_msg),
            countdown=_backoff(self.request.retries),
        )

    self.update_progress(1, 1, "Facility seeding complete.")
    log.info("Task %s — Facility seeding finished successfully.", self.request.id)

    return {
        "status": "success",
        "source": str(source_path),
        "format": file_format,
        "returncode": result.returncode,
    }


@celery_app.task(
    bind=True,
    base=SeedingTask,
    name="seeding.dry_run_check",
    max_retries=1,
    soft_time_limit=120,
    time_limit=150,
)
def dry_run_check(
    self: SeedingTask,
    source: str = _DEFAULT_SOURCE,
    file_format: str = "csv",
) -> dict[str, Any]:
    """
    Validate a registry source file without writing to the database.

    Useful as a pre-flight check before scheduling the real seeding task,
    or to surface validation errors in CI.

    Parameters
    ----------
    source      : Path to the registry file.
    file_format : "csv" or "json".

    Returns
    -------
    dict with keys: status, source, returncode
    """
    log.info(
        "Task %s — Dry-run validation of %s", self.request.id, source,
    )
    self.update_progress(0, 1, f"Validating {source} (dry-run) …")

    env = {**os.environ, "PYTHONUNBUFFERED": "1"}

    cmd = [
        sys.executable,
        str(_SCRIPT),
        "--source", source,
        "--format", file_format,
        "--dry-run",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=env, timeout=100, check=False,
        )
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc, countdown=30)

    if result.stdout:
        for line in result.stdout.strip().splitlines():
            log.info("[script stdout] %s", line)
    if result.stderr:
        for line in result.stderr.strip().splitlines():
            log.warning("[script stderr] %s", line)

    success = result.returncode == 0
    self.update_progress(1, 1, "Dry-run complete.")
    return {
        "status": "success" if success else "validation_failed",
        "source": source,
        "returncode": result.returncode,
    }


# ── Utilities ─────────────────────────────────────────────────────────────────

def _backoff(retries: int, base: int = _RETRY_BASE) -> int:
    """Exponential back-off capped at 10 min."""
    return min(base * (2**retries), 600)
