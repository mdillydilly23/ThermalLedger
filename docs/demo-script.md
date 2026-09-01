# ThermalLedger Showcase Demo Script

## Primary demo: deterministic panel walkthrough

This is the recommended showcase flow. It uses the committed facility fixtures,
deterministic plume overlay, and cached Granite responses, so no third-party
credentials or satellite downloads are needed.

### Preflight

1. Install and start Docker Desktop. Docker Compose, Redis, Python, and Node
   dependencies are provided by the containers; no native `uv`, Redis, or Node
   installation is required.
2. Ensure `.env` keeps the safe defaults:

   ```text
   DATA_SOURCE=local
   GRANITE_MODE=cached
   ```

3. Start the stack:

   ```bash
   docker compose -f infra/docker-compose.yml up --build
   ```

4. Confirm the `redis`, `ml`, `backend`, `worker`, and `frontend` services are
   running. Open `http://localhost:5173`; the Prototype tab should show Backend
   and ML as ready.
5. Keep a small, non-sensitive PDF (under 10 MB) ready for the upload step.

### Walkthrough

1. On **Dashboard**, select a red or amber facility. Explain the EVS, coverage,
   uncertainty interval, and reported-versus-estimated methane value.
2. Point out the plume label: `deterministic_demo_fixture` is a deliberately
   labelled visual aid, not a live satellite retrieval.
3. Open **Upload ESG**, upload the prepared PDF, and show the asynchronous task
   completing with cached Granite-extracted claims and facility matches.
4. Return to the facility panel and select **Generate verification report**.
   Show the cached report and its local audit anchor.
5. Explain that `local_audit_fallback` is an append-only local JSONL record.
   OpenPages and Hyperledger Fabric are future integration points, not active
   production services in this prototype.

## Optional live-data walkthrough

Use this only after completing the deterministic preflight and testing it before
the presentation. Keep `DATA_SOURCE=local`: the prototype processes downloaded
local files and writes its outputs locally. Do not set it to `remote`.

1. Add `COPERNICUS_USERNAME`, `COPERNICUS_PASSWORD`, `CDS_API_KEY`,
   `WATSONX_API_KEY`, and `WATSONX_PROJECT_ID` to `.env` only when needed.
2. Download Sentinel-5P and ERA5 inputs into `data/raw/`, or enable a small,
   single-facility verification run with **Reuse downloaded raw data** disabled.
3. Run and verify one facility before the presentation. Confirm that the
   dashboard shows a persisted `sentinel5p_live_attribution` plume.
4. Keep `GRANITE_MODE=cached` for the primary walkthrough. Set
   `GRANITE_MODE=live` only for a separately rehearsed watsonx demonstration.

## Prototype boundaries

- The deterministic mode is a reliable review-experience demonstration, not a
  live Sentinel-5P retrieval, legal attestation, or blockchain record.
- The live path is a technical prototype, not a regulatory-grade atmospheric
  inversion or production data platform.
- Production additions still needed include upload malware scanning/object
  storage, authentication, observability, deployment hardening, OpenPages case
  creation, and Hyperledger Fabric anchoring.
