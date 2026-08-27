"""Synthetic tests for live plume attribution."""

from __future__ import annotations

from datetime import date

import numpy as np
import xarray as xr

from app.core.config import settings
from app.services.plume_attribution import SOURCE, attribute_facility


def test_synthetic_sentinel_and_era5_files_produce_live_plume(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    sentinel_dir = data_dir / "raw" / "sentinel5p"
    era5_dir = data_dir / "raw" / "era5"
    sentinel_dir.mkdir(parents=True)
    era5_dir.mkdir(parents=True)

    latitudes = np.array([[31.48, 31.50, 31.52], [31.49, 31.51, 31.53]])
    longitudes = np.array([[-103.04, -103.01, -102.98], [-103.03, -103.00, -102.97]])
    methane = np.array([[1820.0, 1835.0, 1860.0], [1822.0, 1845.0, 1885.0]])
    qa = np.ones_like(methane)
    xr.Dataset(
        {
            "latitude": (("scanline", "ground_pixel"), latitudes),
            "longitude": (("scanline", "ground_pixel"), longitudes),
            "methane_mixing_ratio_bias_corrected": (("scanline", "ground_pixel"), methane),
            "qa_value": (("scanline", "ground_pixel"), qa),
        }
    ).to_netcdf(sentinel_dir / "sample_s5p.nc")

    xr.Dataset(
        {
            "u10": (("time",), np.array([4.0, 4.5])),
            "v10": (("time",), np.array([0.2, 0.1])),
        }
    ).to_netcdf(era5_dir / "sample_era5.nc")

    monkeypatch.setattr(settings, "data_dir", data_dir)

    result = attribute_facility(
        facility_id="demo-1",
        facility_name="Demo Facility",
        latitude=31.5,
        longitude=-103.0,
        start=date(2024, 6, 1),
        end=date(2024, 6, 30),
        reported_ch4=1200.0,
        reported_source="Synthetic ESG",
        reported_year=2023,
    )

    assert result["source"] == SOURCE
    assert result["score"]["facility_id"] == "demo-1"
    assert result["score"]["satellite_ch4_estimate"] > 0
    assert result["geojson"]["features"]
    assert result["geojson"]["features"][0]["properties"]["source"] == SOURCE
