# ADR-001 — Async-First Backend from Day One

**Status:** Accepted  
**Date:** Pre-development

## Context

Satellite data downloads (Copernicus API), IBM Granite API calls, Gaussian plume model runs, and watsonx.data federated queries all take between 5 and 60 seconds. A synchronous FastAPI handler blocks the entire server process during that time — every concurrent request stalls, and the frontend appears frozen during the demo.

Retrofitting async onto a sync codebase mid-sprint (around hour 40 of 72) is catastrophic. The fix touches every handler, every service call, and every background task hook.

## Decision

- All FastAPI route handlers use `async def` from the first line written.
- Long-running work (satellite ingest, Granite calls, plume model, report generation) runs as **Celery background tasks** — the endpoint returns a `task_id` immediately, and the frontend polls `GET /tasks/{task_id}` for status.
- All inter-service HTTP calls (backend → ML service, backend → IBM APIs) use `httpx.AsyncClient` inside an async context manager, never `requests`.
- Redis is the Celery broker — one container in docker-compose, no external dependency.

## Consequences

- The demo frontend never shows a frozen spinner waiting on a synchronous call.
- Upload-to-report flow shows live stage-by-stage progress (polling pattern).
- Celery task results are stored in Redis with a short TTL — no persistent task DB needed for a 72-hour sprint.
- `async def` is non-negotiable even for trivial endpoints — consistency prevents accidental sync contamination.
