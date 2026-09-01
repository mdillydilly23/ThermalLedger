"""Reserved task module so the Celery app has a stable scoring extension point."""

from app.core.celery_app import celery_app


@celery_app.task(name="app.tasks.scoring.healthcheck")
def healthcheck() -> dict[str, str]:
    """Minimal task used to verify that the scoring queue is available."""
    return {"status": "ok"}
