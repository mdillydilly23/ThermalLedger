# ThermalLedger

ThermalLedger is a methane-emissions verification proof of concept. It gives a reviewer a facility map, an Emissions Verification Score (EVS), a labelled visual overlay, ESG-claim extraction, and a verification-report workflow.

---

## How IBM Technology Powers ThermalLedger

### The Problem

Corporate methane disclosures are self-reported, rarely third-party verified, and nearly impossible for a single analyst to cross-reference against independent satellite measurements. The result is a systematic gap between what companies report under SEC/CSRD scope-1 rules and what orbital instruments actually detect above their facilities.

### The Solution

ThermalLedger bridges that gap automatically:

1. **Upload any ESG PDF.** IBM Granite (via watsonx.ai) extracts structured methane claims — company name, reporting year, Scope 1 CH₄ tonnes, measurement methodology — in seconds.
2. **Match to satellite observations.** TROPOMI onboard Sentinel-5P measures column-averaged methane globally. ThermalLedger ingests those NetCDF files, applies wind-corrected plume attribution (ERA5 reanalysis), and derives a facility-level CH₄ flux estimate.
3. **Score the discrepancy.** The Emission Verification Score (EVS, 0–100) quantifies alignment between the satellite estimate and the ESG disclosure. A HIGH flag (EVS < 33) means the satellite measurement is more than 2σ above reported — the kind of signal that should trigger a GRC investigation.
4. **Explain the score.** Ask IBM Granite a plain-language question — "Why is this facility flagged?" — and receive a data-grounded answer citing the specific satellite numbers, uncertainty intervals, and flag logic (E-1).
5. **Monitor continuously.** EVS history charts show trend across observation windows, turning a point-in-time audit into an ongoing compliance monitor (E-2).
6. **Anchor to an immutable audit trail.** Each verification result is anchored to Hyperledger Fabric (or a local fallback) so the evidence cannot be retroactively altered.

### IBM Technology Stack

| Component | IBM Technology | Role |
|---|---|---|
| ESG claim extraction | **IBM Granite** (`ibm/granite-3-8b-instruct`) via watsonx.ai | Parse ESG PDFs into structured JSON emission claims |
| EVS explanation chat | **IBM Granite** via watsonx.ai | Answer analyst questions grounded in EVS evidence (E-1) |
| Verification reports | **IBM Granite** via watsonx.ai | Generate SEC/CSRD-aligned HTML attestation reports |
| Scoring service | **watsonx.ai** inference endpoint | EVS computation (plume attribution + σ-scoring) |
| Facility registry | **IBM watsonx.data** (Presto) | Federated SQL query of facility metadata when `WATSONXDATA_HOST` is set (E-4); falls back to Parquet |
| Satellite enrichment | **IBM EIS** (Environmental Intelligence Suite) | Additional TROPOMI CH₄ column data via `/eis/methane/{facility_id}` when `EIS_API_KEY` is set (E-3) |
| GRC workflow trigger | **IBM OpenPages** | Integration point for HIGH-flag cases (pluggable — local fallback in demo) |
| Audit immutability | **Hyperledger Fabric** | Tamper-evident EVS anchoring (local JSONL fallback in demo) |

### Impact

Manually reviewing one facility's ESG claim against satellite data takes a team of analysts 2–3 weeks: finding the right TROPOMI granule, co-locating the wind field, computing the plume back-trajectory, and writing the discrepancy memo. ThermalLedger reduces this to under 60 seconds per facility and scales across a global portfolio of industrial sites without additional headcount.

---

## What works in the panel demo

The default configuration is deliberately deterministic and runs without the large satellite archive or external API credentials:

- A map of the committed facility fixtures, colour-coded by EVS.
- Facility detail with uncertainty and reported-versus-estimated methane.
- A clearly labelled deterministic plume overlay for the selected facility.
- PDF upload that exercises FastAPI → Celery → ML-service cached ESG extraction.
- A cached verification report generated from the facility panel.

The committed fixture scores, plume overlay, ESG extraction, and report are **demonstration outputs**. They are not live Sentinel-5P retrievals, legal attestations, or an active blockchain record. The UI and cached report label that limitation explicitly.

## Quick start — panel demo

Prerequisites: Docker Desktop and Docker Compose.

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up --build
```

Open <http://localhost:5173>. The backend API is at <http://localhost:8000>, with interactive documentation at <http://localhost:8000/docs>.

Suggested presentation flow:

1. Select a red or amber facility marker and explain its EVS, observation coverage, uncertainty interval, and reported comparison.
2. Point out the labelled plume overlay, explaining that it demonstrates the review experience while raw satellite processing is being connected.
3. Open **Upload ESG**, upload any small PDF, and show the cached structured claim returned through the asynchronous task progress UI.
4. Return to the facility detail and choose **Generate verification report** to show the review-ready report view.

For the live prototype walkthrough, use [docs/demo-script.md](docs/demo-script.md).

Stop the stack with `docker compose -f infra/docker-compose.yml down`.

## Native development

Prerequisites: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node 20+, npm, and a local Redis server.

```bash
cp .env.example .env

# terminal 1 — ML service
cd ml && uv sync && uv run uvicorn app.main:app --reload --port 8001

# terminal 2 — backend
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000

# terminal 3 — worker
cd backend && uv run celery -A app.core.celery_app worker --loglevel=info

# terminal 4 — frontend (from repository root)
npm ci && npm run dev
```

The native worker expects Redis at `redis://localhost:6379`; set the usual `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` variables when you replace the demo defaults with a deployed broker.

## Data layout

Small deterministic fixtures are committed under `data/fixtures/` and `data/processed/`. Large inputs are intentionally excluded from Git; see [data/README.md](data/README.md) for the expected local layout and bootstrap commands.

## Live prototype phase

The repository includes a live prototype path for Sentinel-5P/ERA5 ingestion, wind-aware plume attribution, EVS Parquet persistence, and watsonx Granite parsing/report generation. Use the **Prototype** tab to inspect readiness, start verification runs, and see whether the app is using live outputs or deterministic fallbacks.

OpenPages and Hyperledger Fabric are exposed as pluggable integration points. Until a tested live client is added, the prototype writes explicit local audit fallback records under `data/audit/`.

## Repository layout

```text
backend/       FastAPI API gateway and Celery tasks
ml/            FastAPI EVS and cached-Granite service
src/           React + Vite frontend
shared/        Shared Pydantic EVS contract
data/          Committed demo fixtures; untracked raw inputs
infra/         Docker Compose stack
scripts/       Data download and fixture bootstrap scripts
docs/adr/      Architecture decisions from the prototype phase
```

## Environment

Copy [`.env.example`](.env.example) to `.env`. The supplied defaults are the safe demo settings:

```text
DATA_SOURCE=local
GRANITE_MODE=cached
```

Do not commit `.env` or real Copernicus/IBM credentials.
