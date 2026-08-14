# ADR-002 — Pre-Download All Satellite Data; Local Cache Mode

**Status:** Accepted  
**Date:** Pre-development

## Context

The live demo must never wait on an external API. Copernicus API calls, ERA5 CDS downloads, and NASA Earthdata requests have unpredictable latency and occasional rate limits. A 30-second API hang during a 3-minute demo pitch is unrecoverable.

## Decision

- All Copernicus/ERA5/EPA data is **pre-downloaded before the competition starts** using `scripts/download_*.py`.
- The data pipeline module supports a `DATA_SOURCE` environment variable with two values:
  - `local` — all satellite and facility queries are served from `data/` on disk. **This is the default and must be set for demo.**
  - `remote` — live API calls (development and verification only).
- The `DataSourceRouter` class (in `backend/app/core/data_source.py` and `ml/app/core/data_source.py`) wraps every external data call and routes it based on this flag. No call site ever directly checks `DATA_SOURCE` — all routing is centralized.

## Consequences

- Zero demo risk from external API outages, rate limits, or latency.
- Satellite data volume is ~500 MB for 30 days over Permian Basin — acceptable on any laptop.
- `scripts/` must be run once before the sprint starts; this is documented in README.md.
- `data/` is fully gitignored — the bootstrap scripts are the reproducible source of truth.
