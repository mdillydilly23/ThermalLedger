"""
backend/app/tasks/__init__.py
──────────────────────────────
Public surface of the tasks package.

Importing this module ensures all tasks are registered on the shared
celery_app instance.  Workers that start with:

    celery -A app.tasks worker

will auto-discover all tasks defined in this package.
"""

from app.tasks import era5, seeding, sentinel
from app.tasks.celery_app import celery_app

__all__ = ["celery_app", "era5", "seeding", "sentinel"]
