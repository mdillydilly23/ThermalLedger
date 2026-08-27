# Demo data

The small files committed under `data/fixtures/` and `data/processed/` are the
deterministic panel-demo fixture. They let the map, EVS detail, plume overlay,
ESG extraction, and cached report run without credentials or large downloads.

`data/raw/` is intentionally untracked. Download any real inputs there:

```text
data/raw/sentinel5p/   Sentinel-5P L2 methane products
data/raw/era5/         ERA5 wind fields
data/esg_pdfs/         optional source ESG PDFs
```

Run `python scripts/download_sentinel5p.py` and
`python scripts/download_era5.py` after configuring the relevant credentials.
Those data files are not yet used to calculate the committed demo EVS values;
the real raster-to-plume attribution implementation is the next technical
phase. The UI labels its plume source as `deterministic_demo_fixture` so it is
never represented as a live satellite retrieval.
