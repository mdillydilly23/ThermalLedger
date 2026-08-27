# ThermalLedger Prototype Demo Script

## Preflight

1. Copy `.env.example` to `.env`.
2. Set `COPERNICUS_USERNAME`, `COPERNICUS_PASSWORD`, `CDS_API_KEY`, `WATSONX_API_KEY`, and `WATSONX_PROJECT_ID`.
3. Set `GRANITE_MODE=live` for live Granite, or `GRANITE_MODE=cached` for the deterministic fallback.
4. Start the stack:

```bash
docker compose -f infra/docker-compose.yml up --build
```

Open `http://localhost:5173` and confirm `Prototype > Readiness` shows backend and ML as ready.

## Walkthrough

1. Open **Prototype** and review credential/data status.
2. Keep **Reuse downloaded raw data** enabled if Sentinel-5P and ERA5 files are already present under `data/raw/`.
3. Start a verification run for all facilities or a selected facility.
4. Return to **Dashboard**, select the updated facility, and point out the plume source label:
   - `sentinel5p_live_attribution` means a processed live-source plume is being shown.
   - `deterministic_demo_fixture` means the dashboard is using the safe fallback.
5. Open **Upload ESG**, upload a PDF, and show Granite-extracted methane claims plus facility matches.
6. Generate the verification report from the facility panel.
7. Point out the audit label:
   - `local_audit_fallback` is an append-only local JSONL audit trail under `data/audit/`.
   - Hyperledger/OpenPages clients remain pluggable production integration points.

## Prototype Boundaries

- Live path: Sentinel-5P/ERA5 ingestion, ML plume attribution, EVS Parquet persistence, watsonx Granite parsing/report generation when credentials are present.
- Fallback path: cached Granite outputs and deterministic plume overlay.
- Production gaps: regulatory-grade atmospheric inversion, object storage and malware scanning for uploads, live OpenPages case creation, live Hyperledger Fabric anchoring, auth, observability, and deployment hardening.
