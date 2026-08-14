# ThermalLedger

**AI Carbon Credit Verifier using Satellite Emissions Data**

Replacing self-reported corporate emissions with satellite-verified ground truth — making the $2B+ voluntary carbon market trustworthy, auditable, and legally defensible.

**Stack:** ESA Sentinel-5P · IBM Granite (watsonx.ai) · IBM EIS · IBM OpenPages · Hyperledger Fabric · React + MapLibre GL

---

## Repo Structure

```
thermal_ledger/
├── backend/        # FastAPI — data ingestion, EVS scoring API, IBM integrations
├── ml/             # FastAPI — Gaussian plume model, EVS scorer, Granite report gen
├── frontend/       # React + Vite — facility map, upload flow, report viewer
├── shared/         # EVS schema (Pydantic + TS), API contract types
├── data/           # .gitignored — satellite data, Parquet files, ESG PDFs
│   ├── raw/        #   Sentinel-5P NetCDF, ECOSTRESS GeoTIFF, ERA5 wind fields
│   ├── processed/  #   facility.parquet, ch4_attributed.parquet, evs_scores.parquet
│   └── esg_pdfs/   #   staged corporate ESG PDFs for Granite ingestion
├── infra/          # docker-compose.yml, Dockerfiles
├── scripts/        # one-shot data bootstrap (download ERA5, seed facility CSV)
└── docs/adr/       # Architecture Decision Records
```

---

## Quick Start

### Prerequisites
- Python 3.11+ with [uv](https://github.com/astral-sh/uv)
- Node 20+ with [pnpm](https://pnpm.io)
- Docker + Docker Compose (optional, for containerized dev)

### 1 · Clone and configure environment

```bash
git clone <repo-url>
cd thermal_ledger
cp .env.example .env
# Fill in .env with your API keys
```

### 2 · Start with Docker Compose (recommended)

```bash
docker compose up
```

Services will be available at:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- ML service: http://localhost:8001 (internal only)
- API docs: http://localhost:8000/docs

### 3 · Start services individually (without Docker)

```bash
# ML service
cd ml && uv sync && uv run fastapi dev app/main.py --port 8001

# Backend service (new terminal)
cd backend && uv sync && uv run fastapi dev app/main.py --port 8000

# Frontend (new terminal)
cd frontend && pnpm install && pnpm dev
```

### 4 · Download satellite data (first time only)

```bash
# Download 30-day Sentinel-5P CH4 over Permian Basin
python scripts/download_sentinel5p.py

# Download ERA5 wind fields for same window
python scripts/download_era5.py

# Seed facility master table from EPA GHGRP + EU ETS CSVs
python scripts/seed_facilities.py
```

---

## Architecture Decision Records

| ADR | Decision |
|-----|----------|
| [ADR-001](docs/adr/001-async-first-backend.md) | Async-first FastAPI + Celery background tasks |
| [ADR-002](docs/adr/002-local-cache-mode.md) | DATA_SOURCE=local\|remote toggle for demo safety |
| [ADR-003](docs/adr/003-evs-shared-schema.md) | EVS object as shared Pydantic + TypeScript contract |
| [ADR-004](docs/adr/004-pydantic-api-shapes.md) | All API shapes as Pydantic models, OpenAPI-generated TS types |
| [ADR-005](docs/adr/005-map-provider.md) | MapLibre GL JS + Deck.gl HeatmapLayer (zero cost, zero rate limits) |
| [ADR-006](docs/adr/006-granite-cache.md) | Granite batch-and-cache; demo always runs against pre-generated outputs |
| [ADR-007](docs/adr/007-monorepo.md) | Single monorepo, one docker-compose, shared data directory |

---

## Environment Variables

See [`.env.example`](.env.example) for the full schema with comments.

Key toggles:
- `DATA_SOURCE=local` — serves satellite data from `./data/` (always use for demo)
- `GRANITE_MODE=cached` — serves pre-generated Granite outputs from `ml/cache/`
