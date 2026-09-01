# ADR-006 — Granite Integration: Batch-and-Cache; Never Live During Demo

**Status:** Accepted  
**Date:** Pre-development

## Context

IBM watsonx.ai hackathon credits are finite and unpredictable. Granite API latency for a full ESG PDF parse (80+ pages) is 10–30 seconds per document. Running Granite live during a 3-minute pitch introduces two failure modes:
1. API credit exhaustion mid-demo
2. Latency spike that breaks the demo timing script

## Decision

- All Granite ESG parsing calls are **batched during Phase 2 of the sprint** (hours 16–36) and results cached as JSON in `ml/cache/granite/`.
- The Granite report generation for the **hero case** (best discrepancy finding) is pre-generated and stored in `ml/cache/reports/`.
- The `GRANITE_MODE` environment variable controls behavior:
  - `cached` — ML service reads from `ml/cache/` (always set for demo)
  - `live` — ML service calls watsonx.ai in real time (development only)
- The `GraniteClient` class in `ml/app/services/granite.py` is the only code that reads `GRANITE_MODE`. All callers use `GraniteClient` — no direct watsonx SDK calls at the route level.
- The demo "upload PDF → Granite parses → score returned" flow plays against cached outputs. The pipeline stage indicators tick through in real time (with realistic delays) but the underlying data is pre-computed.

## Cache Layout

```
ml/cache/
├── granite/
│   ├── pioneer_2023_esg.json        # extracted emission claims, citation-linked
│   ├── oxy_2023_esg.json
│   └── exxon_2023_esg.json
└── reports/
    ├── hero_facility_report.html    # pre-generated Granite verification report
    └── hero_facility_report.pdf
```

## Consequences

- Demo is fully deterministic — same result every run, zero API dependency.
- Granite still runs live during Phase 2 development — the real extraction and report are genuine AI outputs, just pre-computed.
- If the demo environment has reliable watsonx.ai access and credits to spare, `GRANITE_MODE=live` can be enabled for a secondary upload demo. Default is always `cached`.
