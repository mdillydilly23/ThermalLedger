"""
ADR-002: DataSourceRouter — centralizes the local vs remote data routing decision.

All code that needs external data calls this router.
No call site reads DATA_SOURCE directly — routing is handled here exclusively.
"""

from pathlib import Path
from typing import Protocol

from app.core.config import settings


class SatelliteDataProvider(Protocol):
    async def get_ch4_raster(self, facility_id: str, start: str, end: str) -> Path: ...
    async def get_era5_winds(self, facility_id: str, start: str, end: str) -> Path: ...


class LocalDataProvider:
    """Serves pre-downloaded satellite data from disk. Zero external API dependency."""

    def __init__(self, data_dir: Path):
        self._dir = data_dir

    async def get_ch4_raster(self, facility_id: str, start: str, end: str) -> Path:
        path = self._dir / "raw" / "sentinel5p" / f"{facility_id}_{start}_{end}_ch4.nc"
        if not path.exists():
            raise FileNotFoundError(
                f"Local CH4 raster not found: {path}\n"
                "Run scripts/download_sentinel5p.py to populate data/raw/sentinel5p/"
            )
        return path

    async def get_era5_winds(self, facility_id: str, start: str, end: str) -> Path:
        path = self._dir / "raw" / "era5" / f"{facility_id}_{start}_{end}_wind.nc"
        if not path.exists():
            raise FileNotFoundError(
                f"Local ERA5 wind file not found: {path}\n"
                "Run scripts/download_era5.py to populate data/raw/era5/"
            )
        return path


class RemoteDataProvider:
    """Live calls to Copernicus and CDS APIs. Development use only — never during demo."""

    async def get_ch4_raster(self, facility_id: str, start: str, end: str) -> Path:
        # TODO: implement Copernicus Data Space STAC API call
        raise NotImplementedError("Remote Copernicus integration not yet implemented")

    async def get_era5_winds(self, facility_id: str, start: str, end: str) -> Path:
        # TODO: implement ECMWF CDS API call
        raise NotImplementedError("Remote CDS ERA5 integration not yet implemented")


def get_data_provider() -> SatelliteDataProvider:
    """FastAPI dependency — inject into route handlers."""
    if settings.data_source == "local":
        return LocalDataProvider(settings.data_dir)
    return RemoteDataProvider()
