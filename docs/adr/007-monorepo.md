# ADR-007 — Monorepo Structure

**Status:** Accepted  
**Date:** Pre-development

## Context

The project has three services (backend, ML, frontend) built by one team in 72 hours. Splitting them into separate repos introduces overhead: cross-repo branch coordination, separate clone steps, import path gymnastics for shared types. In a sprint, any friction that isn't product work is waste.

## Decision

Single Git repository. One `docker-compose.yml`. Shared `data/` directory bind-mounted into the containers that need it.

```
thermal_ledger/
├── backend/          # FastAPI service — Copernicus ingest, scoring API, IBM integrations
│   ├── app/
│   │   ├── api/routes/   # route handlers (async def only)
│   │   ├── core/         # config, data_source router, celery app
│   │   ├── models/       # Pydantic request/response models
│   │   ├── services/     # watsonx.data, OpenPages, Fabric, EIS clients
│   │   └── tasks/        # Celery task definitions
│   ├── pyproject.toml
│   └── Dockerfile
├── ml/               # FastAPI service — plume model, EVS scorer, Granite
│   ├── app/
│   │   ├── api/routes/
│   │   ├── core/
│   │   ├── models/
│   │   └── services/     # plume model, EVS scorer, GraniteClient
│   ├── cache/            # pre-generated Granite outputs (committed)
│   │   ├── granite/
│   │   └── reports/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/         # React + Vite
│   ├── src/
│   │   ├── components/   # map/, dashboard/, upload/
│   │   ├── pages/
│   │   ├── hooks/        # useEVSData, useFacilities, useTask
│   │   ├── types/        # api.ts (generated), evs.ts (re-export)
│   │   └── lib/          # API client, constants
│   ├── package.json
│   └── Dockerfile
├── shared/           # language-agnostic contracts
│   └── evs_schema.py     # canonical Pydantic EVS model (imported by backend + ml)
├── data/             # .gitignored — local satellite data
├── infra/
│   └── docker-compose.yml
├── scripts/          # bootstrap data downloads
├── docs/adr/         # this file and siblings
├── .env.example
├── .gitignore
└── README.md
```

## Service Communication

```
Browser → backend:8000 → ml:8001        (internal Docker network)
                       → IBM watsonx.ai
                       → IBM EIS
                       → IBM OpenPages
                       → Hyperledger Fabric
```

The ML service is **not exposed to the browser**. The backend is the single API gateway for the frontend.

## Consequences

- `git clone` + `docker compose up` = full working environment.
- Shared `evs_schema.py` is on the Python path for both `backend` and `ml` — no package publishing needed during the sprint.
- `data/` is bind-mounted, not copied — satellite data persists across container rebuilds.
- One branch, one PR, one merge to demo from. No cross-repo sync overhead.
