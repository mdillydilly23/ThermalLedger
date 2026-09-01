"""Sentinel-5P/ERA5 plume attribution for the live prototype."""

from __future__ import annotations

import logging
import math
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from app.core.config import settings
from app.services.evs_scorer import compute_evs

SOURCE = "sentinel5p_live_attribution"
log = logging.getLogger(__name__)


def attribute_facility(
    facility_id: str,
    facility_name: str,
    latitude: float,
    longitude: float,
    start: date,
    end: date,
    reported_ch4: float | None,
    reported_source: str | None,
    reported_year: int | None,
) -> dict[str, Any]:
    """Compute a prototype live EVS score and plume GeoJSON for one facility."""
    sentinel_files = _raw_files(settings.data_dir / "raw" / "sentinel5p", ("*.nc", "*.nc4"))
    if not sentinel_files:
        raise FileNotFoundError(
            f"No Sentinel-5P NetCDF files found under {settings.data_dir / 'raw' / 'sentinel5p'}."
        )

    observations = _collect_ch4_observations(sentinel_files, latitude, longitude)
    if observations["values"].size == 0:
        raise ValueError(f"No QA-passing Sentinel-5P CH4 observations found near {facility_id}.")

    wind = _mean_wind(settings.data_dir / "raw" / "era5")
    wind_speed = max(0.5, math.hypot(wind["u"], wind["v"]))
    weighted_enhancement = _weighted_enhancement(
        latitude=latitude,
        longitude=longitude,
        lats=observations["lats"],
        lons=observations["lons"],
        enhancements=observations["enhancements"],
        wind_u=wind["u"],
        wind_v=wind["v"],
    )

    estimate = round(max(0.0, weighted_enhancement * wind_speed * 45.0), 1)
    uncertainty = max(500.0, estimate * 0.35)
    total_days = max(1, (end - start).days + 1)
    valid_days = min(total_days, max(1, observations["file_count"]))

    score = compute_evs(
        facility_id=facility_id,
        facility_name=facility_name,
        latitude=latitude,
        longitude=longitude,
        observation_start=start,
        observation_end=end,
        days_with_valid_retrievals=valid_days,
        total_days=total_days,
        satellite_ch4_estimate=estimate,
        satellite_uncertainty_low=round(max(0.0, estimate - 1.96 * uncertainty), 1),
        satellite_uncertainty_high=round(estimate + 1.96 * uncertainty, 1),
        reported_ch4=reported_ch4,
        reported_source=reported_source,
        reported_year=reported_year,
    )

    return {
        "facility_id": facility_id,
        "source": SOURCE,
        "method_notes": [
            "Prototype attribution from QA-filtered Sentinel-5P CH4 pixels near facility.",
            wind["note"],
            "Flux conversion is a transparent prototype heuristic, not a regulatory-grade inversion.",
        ],
        "score": score.model_dump(mode="json"),
        "geojson": _plume_geojson(
            facility_id=facility_id,
            lats=observations["lats"],
            lons=observations["lons"],
            enhancements=observations["enhancements"],
            wind_speed=wind_speed,
        ),
    }


def _collect_ch4_observations(
    files: list[Path],
    latitude: float,
    longitude: float,
    radius_deg: float = 0.5,
) -> dict[str, Any]:
    lats: list[np.ndarray] = []
    lons: list[np.ndarray] = []
    values: list[np.ndarray] = []
    files_with_points = 0

    for path in files:
        arrays = _read_sentinel_arrays(path)
        if arrays is None:
            continue

        lat = arrays["lat"]
        lon = arrays["lon"]
        ch4 = arrays["ch4"]
        qa = arrays.get("qa")

        mask = (
            np.isfinite(lat)
            & np.isfinite(lon)
            & np.isfinite(ch4)
            & (np.abs(lat - latitude) <= radius_deg)
            & (np.abs(lon - longitude) <= radius_deg)
        )
        if qa is not None:
            mask &= np.isfinite(qa) & (qa >= 0.5)

        if not np.any(mask):
            continue

        files_with_points += 1
        lats.append(lat[mask])
        lons.append(lon[mask])
        values.append(ch4[mask])

    if not values:
        return {
            "lats": np.array([], dtype=float),
            "lons": np.array([], dtype=float),
            "values": np.array([], dtype=float),
            "enhancements": np.array([], dtype=float),
            "file_count": 0,
        }

    all_lats = np.concatenate(lats)
    all_lons = np.concatenate(lons)
    all_values = np.concatenate(values)
    background = float(np.nanpercentile(all_values, 20))
    enhancements = np.maximum(all_values - background, 0.0)
    return {
        "lats": all_lats,
        "lons": all_lons,
        "values": all_values,
        "enhancements": enhancements,
        "file_count": files_with_points,
    }


def _read_sentinel_arrays(path: Path) -> dict[str, np.ndarray] | None:
    for group in (None, "PRODUCT"):
        try:
            dataset = xr.open_dataset(path, group=group) if group else xr.open_dataset(path)
        except (OSError, ValueError) as exc:
            log.debug("Skipping Sentinel-5P candidate %s group=%s: %s", path, group, exc)
            continue

        try:
            lat = _find_array(dataset, ("latitude", "lat"))
            lon = _find_array(dataset, ("longitude", "lon"))
            ch4 = _find_array(
                dataset,
                (
                    "methane_mixing_ratio_bias_corrected",
                    "xch4",
                    "ch4",
                    "CH4_column_volume_mixing_ratio_dry_air",
                ),
            )
            if lat is None or lon is None or ch4 is None:
                continue
            lat_values = np.asarray(lat, dtype=float).reshape(-1)
            lon_values = np.asarray(lon, dtype=float).reshape(-1)
            ch4_values = np.asarray(ch4, dtype=float).reshape(-1)
            if lat_values.size != ch4_values.size or lon_values.size != ch4_values.size:
                log.debug("Skipping Sentinel-5P candidate %s group=%s due to shape mismatch.", path, group)
                continue
            qa = _find_array(dataset, ("qa_value", "qa"))
            qa_values = None if qa is None else np.asarray(qa, dtype=float).reshape(-1)
            if qa_values is not None and qa_values.size != ch4_values.size:
                qa_values = None
            return {
                "lat": lat_values,
                "lon": lon_values,
                "ch4": ch4_values,
                "qa": qa_values,
            }
        finally:
            dataset.close()
    return None


def _mean_wind(root: Path) -> dict[str, Any]:
    files = _raw_files(root, ("*.nc", "*.nc4"))
    if not files:
        return {
            "u": 3.0,
            "v": 0.0,
            "note": "ERA5 wind file missing; used explicit 3 m/s eastward prototype default.",
        }

    u_values: list[np.ndarray] = []
    v_values: list[np.ndarray] = []
    for path in files:
        try:
            dataset = xr.open_dataset(path)
        except (OSError, ValueError) as exc:
            log.debug("Skipping ERA5 candidate %s: %s", path, exc)
            continue
        try:
            u = _find_array(dataset, ("u10", "10m_u_component_of_wind", "u_component_of_wind_10m"))
            v = _find_array(dataset, ("v10", "10m_v_component_of_wind", "v_component_of_wind_10m"))
            if u is not None:
                u_values.append(np.asarray(u, dtype=float).reshape(-1))
            if v is not None:
                v_values.append(np.asarray(v, dtype=float).reshape(-1))
        finally:
            dataset.close()

    if not u_values or not v_values:
        return {
            "u": 3.0,
            "v": 0.0,
            "note": "ERA5 wind variables missing; used explicit 3 m/s eastward prototype default.",
        }

    return {
        "u": float(np.nanmean(np.concatenate(u_values))),
        "v": float(np.nanmean(np.concatenate(v_values))),
        "note": "ERA5 10m wind vectors used for plume weighting.",
    }


def _weighted_enhancement(
    latitude: float,
    longitude: float,
    lats: np.ndarray,
    lons: np.ndarray,
    enhancements: np.ndarray,
    wind_u: float,
    wind_v: float,
) -> float:
    if enhancements.size == 0:
        return 0.0

    dx = (lons - longitude) * 111.0 * math.cos(math.radians(latitude))
    dy = (lats - latitude) * 111.0
    speed = max(0.5, math.hypot(wind_u, wind_v))
    unit_x = wind_u / speed
    unit_y = wind_v / speed
    downwind = dx * unit_x + dy * unit_y
    crosswind = np.abs(-dx * unit_y + dy * unit_x)
    weights = np.exp(-((crosswind / 12.0) ** 2)) * np.where(downwind >= -5.0, 1.0, 0.25)
    if float(np.sum(weights)) <= 0:
        return float(np.nanmean(enhancements))
    return float(np.average(enhancements, weights=weights))


def _plume_geojson(
    facility_id: str,
    lats: np.ndarray,
    lons: np.ndarray,
    enhancements: np.ndarray,
    wind_speed: float,
    max_points: int = 500,
) -> dict[str, Any]:
    if enhancements.size == 0:
        features: list[dict[str, Any]] = []
    else:
        max_enhancement = max(float(np.nanmax(enhancements)), 1.0)
        order = np.argsort(enhancements)[::-1]
        step = max(1, math.ceil(len(order) / max_points))
        features = []
        for index in order[::step]:
            enhancement = float(enhancements[index])
            if enhancement <= 0:
                continue
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(lons[index]), float(lats[index])],
                },
                "properties": {
                    "weight": round(enhancement / max_enhancement, 4),
                    "ch4_enhancement_ppb": round(enhancement, 3),
                    "wind_speed_m_s": round(wind_speed, 3),
                    "source": SOURCE,
                },
            })

    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "facility_id": facility_id,
            "source": SOURCE,
        },
    }


def _find_array(dataset: xr.Dataset, names: tuple[str, ...]) -> np.ndarray | None:
    lookup = {name.lower(): name for name in [*dataset.data_vars, *dataset.coords]}
    for candidate in names:
        actual = lookup.get(candidate.lower())
        if actual is not None:
            return dataset[actual].values
    return None


def _raw_files(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for pattern in patterns:
        files.extend(path for path in root.rglob(pattern) if path.is_file())
    return sorted(files)
