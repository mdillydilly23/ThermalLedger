"""
backend/app/tasks/celery_app.py
────────────────────────────────
Dedicated Celery application instance for Phase 1 data-ingestion tasks.

This module re-exports the shared `celery_app` from `app.core.celery_app`
and extends its configuration with the two queues used by ingestion work:

  downloads  – heavy, long-running API downloads (Sentinel-5P, ERA5)
  seeding    – fast, database-bound facility seeding

Workers can be targeted at a specific queue:
  celery -A app.tasks.celery_app worker -Q downloads -c 2
  celery -A app.tasks.celery_app worker -Q seeding   -c 4
"""

from kombu import Queue  # type: ignore[import]

from app.core.celery_app import celery_app  # re-export shared instance

# ── Queue definitions ─────────────────────────────────────────────────────────
celery_app.conf.task_queues = (
    Queue("downloads"),   # CPU-light, network-heavy — keep concurrency low
    Queue("seeding"),     # DB-bound, fast — higher concurrency acceptable
    Queue("celery"),      # default queue (scoring, reports, ESG — from core config)
)
celery_app.conf.task_default_queue = "celery"

# ── Make tasks discoverable from this module's package ───────────────────────
# Add ingestion task modules to the shared include list so `celery_app.autodiscover`
# works whether workers start from `app.core.celery_app` or this module.
_NEW_INCLUDES = [
    "app.tasks.sentinel",
    "app.tasks.era5",
    "app.tasks.seeding",
]
existing: list[str] = list(celery_app.conf.include or [])
for _mod in _NEW_INCLUDES:
    if _mod not in existing:
        existing.append(_mod)
celery_app.conf.include = existing

# Re-export so callers can do: from app.tasks.celery_app import celery_app
__all__ = ["celery_app"]
