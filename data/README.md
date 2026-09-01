# Demo and prototype data

## Deterministic panel demo

The small committed files in `data/fixtures/` and `data/processed/` power the
credential-free showcase. They provide the facility map, EVS detail,
deterministic plume overlay, cached ESG extraction, and cached verification
report. The UI labels this plume source as `deterministic_demo_fixture`; it is
never presented as a live satellite retrieval.

## Optional live-data prototype

The live verification path reads local raw data, runs wind-aware plume
attribution, and persists updated EVS scores and GeoJSON plumes under
`data/processed/`. Leave `DATA_SOURCE=local` enabled for this workflow.

`data/raw/` is intentionally untracked. Place external inputs here:

```text
data/raw/sentinel5p/   Sentinel-5P L2 methane products
data/raw/era5/         ERA5 wind fields
data/esg_pdfs/         optional source ESG PDFs
```

Configure the required credentials, then use `scripts/download_sentinel5p.py`
and `scripts/download_era5.py`, or start a verification run with raw-data reuse
disabled. Download and validate inputs before a presentation; do not rely on
external APIs during the showcase.

The live path is a prototype, not a regulatory-grade atmospheric inversion.
Uploads, generated plumes, audit records, and live outputs are ignored by Git
and stay local to the machine running the demo.
