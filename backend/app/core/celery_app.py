"""
ADR-001: Celery app — async background task broker.
All long-running work (Granite calls, plume model, report gen, blockchain anchor)
dispatches here so FastAPI handlers return immediately.
"""

import os

from celery import Celery

# Redis is local by default for native development. Compose supplies the
# service-hostname URLs to the API and worker containers.
celery_app = Celery(
    "thermalledger",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    include=[
        "app.tasks.scoring",
        "app.tasks.reports",
        "app.tasks.esg",
        "app.tasks.verification",
        # Phase 1 — data ingestion tasks
        "app.tasks.sentinel",
        "app.tasks.era5",
        "app.tasks.seeding",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,  # 1 hour TTL — sufficient for a sprint demo
    task_track_started=True,
)
