# ADR-004 — Pydantic Models for All API Shapes; OpenAPI-Generated TypeScript Types

**Status:** Accepted  
**Date:** Pre-development

## Context

Without a single source of truth for API shapes, the frontend and backend drift apart silently. A field rename on the backend breaks the frontend at runtime, not at compile time. In a 72-hour sprint this is discovered during demo rehearsal.

FastAPI natively generates an OpenAPI 3.1 spec from Pydantic models with zero extra configuration. TypeScript types can be generated from that spec automatically.

## Decision

- Every FastAPI request body and response object is a **Pydantic v2 `BaseModel`** — no raw dicts, no `Any` return types.
- The backend's OpenAPI spec is served at `GET /openapi.json`.
- Frontend TypeScript types are generated from that spec using `openapi-typescript`:
  ```bash
  pnpm run generate:types
  # runs: openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts
  ```
- `src/types/api.ts` is committed — it's the contract. It is regenerated whenever backend models change.
- `src/types/evs.ts` re-exports the `EVSScore` interface from `api.ts` — no manual duplication.

## Consequences

- Backend model change → regenerate types → TypeScript compiler catches every frontend mismatch before runtime.
- OpenAPI docs at `/docs` are always accurate — useful during the sprint for verifying endpoint behavior.
- Zero hand-written TypeScript API types — all derived from Python Pydantic models.
