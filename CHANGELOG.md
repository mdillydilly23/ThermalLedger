# Changelog

All notable changes to ThermalLedger are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added
- `ErrorBoundary` class component wrapping the full React tree in `src/main.tsx` — prevents blank white screen on unhandled render errors.
- Exponential backoff (capped at 30 s) for task-poll retries in `src/hooks/useTask.ts`.
- This `CHANGELOG.md` to document project progression.

### Fixed
- Removed spurious `_load_facilities.cache_clear()` call in `parquet_store.upsert_evs_scores` — the facilities Parquet is only written by seeding scripts, not EVS upserts.

---

## [0.3.0] — Demo Hardening

### Added
- Multi-stage Docker build (nginx serving `dist/`) replacing the Vite dev-server container.
- `infra/nginx.conf` with `/api/` proxy pass to the backend service.
- Static API-key guard (`X-Api-Key` header) on all mutating endpoints via `backend/app/api/deps.py`.
- `ALLOWED_ORIGINS` environment variable for runtime CORS configuration (defaults to `localhost:5173`).
- Docker Compose `worker` healthcheck using `celery inspect ping`; backend service waits for a healthy worker before accepting traffic.

### Changed
- Granite model ID updated from deprecated `ibm/granite-13b-instruct-v2` to `ibm/granite-3-8b-instruct`.
- `DEMO_API_KEY`, `ALLOWED_ORIGINS`, and `GRANITE_MODEL_ID` added to `.env.example` with comments.

### Removed
- Unused `axios` and `recharts` production dependencies from `package.json`.
- Unused `sqlalchemy`, `ibm-watson`, and `ibm-platform-services` from `backend/pyproject.toml`.

---

## [0.2.0] — Live Verification Path

### Added
- Celery task pipeline: `run_verification` → Sentinel-5P download → ERA5 wind correction → EVS computation → audit anchor.
- Prototype page (`/prototype`) with real-time task progress indicator and credential readiness panel.
- Parquet-backed EVS score store (`data/processed/evs_scores.parquet`) with atomic upsert.
- `GET /facilities/{id}/history` groundwork (history array placeholder in fixture).
- CI workflow (`.github/workflows/verify.yml`) running pytest for backend + ML, TypeScript check for frontend.

### Changed
- Map initial view changed to world overview (`longitude: -20, latitude: 45, zoom: 2.5`) so all 15 global facilities are visible on first load.
- Report iframe height increased to 360 px with vertical scroll affordance.
- Prototype page default facility selector changed from hard-coded `EPA-GHGRP-TX-001` to `all`.

### Fixed
- Startup lifespan check now verifies both `facilities.parquet` and `evs_scores.parquet` exist before accepting traffic.
- `get_facility_summaries()` returns an empty list (graceful degradation) if fixture files are missing.

---

## [0.1.0] — IBM AI Builders Challenge Prototype

### Added
- FastAPI backend with `/facilities`, `/esg`, `/verification`, `/tasks`, and `/reports` route groups.
- ML service with IBM Granite (`ibm-watsonx-ai`) for structured ESG claim extraction and HTML report generation.
- React + TypeScript frontend: Dashboard (map + facility panel), ESG Upload, and Prototype pages.
- Deck.gl / MapLibre satellite map with EVS-coloured facility markers.
- Shared `EVSScore` / `FacilitySummary` Pydantic schema (`shared/evs_schema.py`).
- Demo fixture Parquet files covering 15 facilities across the USA and Europe.
- Cached Granite fallback (`GRANITE_MODE=cached`) for offline / judge-demo scenarios.
- Architecture Decision Records (ADRs) documenting key design choices.
- Docker Compose stack: backend, ML service, Celery worker, Redis.
