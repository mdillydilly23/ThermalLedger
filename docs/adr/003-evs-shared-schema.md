# ADR-003 — EVS Object as Shared Schema Contract

**Status:** Accepted  
**Date:** Pre-development

## Context

The Emission Verification Score (EVS) object is consumed by six distinct system components:
1. ML service — computes and emits it
2. Backend scoring engine — receives and stores it
3. watsonx.data query layer — queries across it
4. Granite report generator — reads it to produce prose
5. Blockchain anchor service — hashes and anchors it
6. Frontend map and charts — renders it

If each component defines this shape independently, incompatible field names and types accumulate silently. Marshalling bugs discovered at hour 40 of a 72-hour sprint are sprint-killers.

## Decision

- The canonical EVS schema is defined **once** in `shared/evs_schema.py` as a Pydantic v2 model.
- All Python services import `EVSScore` and `DiscrepancyFlag` from `shared/evs_schema.py` — never redefined inline.
- The TypeScript interface in `frontend/src/types/evs.ts` is **generated** from the OpenAPI spec produced by the backend (see ADR-004) — not hand-written.
- The EVS object is immutable after creation by the ML service. Backend and frontend read it; only the ML service writes it.

## Canonical Fields

| Field | Type | Description |
|---|---|---|
| `facility_id` | string | EU ETS or EPA GHGRP ID |
| `satellite_ch4_estimate` | float | Satellite-derived CH₄, tonnes/year |
| `satellite_uncertainty_low/high` | float | 95% CI bounds |
| `reported_ch4` | float? | Corporate self-reported CH₄ |
| `delta_pct` | float? | ((satellite − reported) / reported) × 100 |
| `sigma_deviation` | float? | σ deviation of satellite from reported |
| `evs` | float 0–100 | Emission Verification Score |
| `flag` | enum | `clear` / `watch` / `high` |
| `coverage_pct` | float | % of window with valid TROPOMI retrievals |
| `blockchain_tx_id` | string? | Hyperledger Fabric tx hash |

## Consequences

- No data marshalling bugs between layers.
- OpenAPI spec is always in sync with what the backend actually returns.
- Frontend TypeScript types are regenerated with `pnpm run generate:types` — one command.
