#!/usr/bin/env python3
"""
scripts/download_era5.py
─────────────────────────
Download ERA5 reanalysis data from the ECMWF Copernicus Climate Data Store (CDS)
using the official `cdsapi` client library.

Usage
-----
python scripts/download_era5.py \\
    --start-date  2024-01-01 \\
    --end-date    2024-01-31 \\
    --variables   2m_temperature,10m_u_component_of_wind,10m_v_component_of_wind \\
    --bbox="-5.0/35.0/40.0/72.0" \\
    --format      netcdf \\
    --out-dir     data/raw/era5

Note: use ``--bbox=VALUE`` (equals sign) when the bbox starts with a negative
number, otherwise the shell passes it as an unknown flag.

Environment variables (set in .env or shell)
--------------------------------------------
CDS_API_URL   – CDS API base URL (default: https://cds.climate.copernicus.eu/api)
CDS_API_KEY   – CDS API personal access key (UID:token format)

Note: cdsapi >=0.7 uses ecmwf-datastores-client internally. The client reads
ECMWF_DATASTORES_URL and ECMWF_DATASTORES_KEY env vars directly; this script
sets them from CDS_API_URL / CDS_API_KEY before constructing the client.

Supported variables (ERA5 single-level)
----------------------------------------
2m_temperature, 10m_u_component_of_wind, 10m_v_component_of_wind,
total_precipitation, surface_pressure, boundary_layer_height,
mean_sea_level_pressure, 2m_dewpoint_temperature

Format choices: netcdf | grib
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("era5.downloader")

# ── Constants ────────────────────────────────────────────────────────────────
DEFAULT_CDS_URL = "https://cds.climate.copernicus.eu/api"
CDS_DATASET = "reanalysis-era5-single-levels"

SUPPORTED_VARIABLES = [
    "2m_temperature",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "total_precipitation",
    "surface_pressure",
    "boundary_layer_height",
    "mean_sea_level_pressure",
    "2m_dewpoint_temperature",
]

# Hourly time steps (UTC) included in every request
DEFAULT_TIMES = [f"{h:02d}:00" for h in range(24)]

MAX_RETRIES = 4
RETRY_BASE_SLEEP = 10  # seconds


# ── Date utilities ────────────────────────────────────────────────────────────

def _date_range_months(start: datetime, end: datetime) -> list[tuple[str, list[str]]]:
    """
    Split a date range into (year-month, [days]) tuples so each CDS request
    stays within a single calendar month — the CDS API performs best this way.
    """
    result: list[tuple[str, list[str]]] = []
    current = start.replace(day=1)
    while current <= end:
        year_month = current.strftime("%Y-%m")
        days_in_month: list[str] = []
        day = current
        while day.month == current.month and day <= end:
            if day >= start:
                days_in_month.append(day.strftime("%d"))
            day += timedelta(days=1)
        if days_in_month:
            result.append((year_month, days_in_month))
        # Advance to first day of next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return result


def _parse_bbox_cds(raw: str) -> list[float]:
    """
    Parse a bounding box string into [north, west, south, east] order,
    which is the order expected by the CDS area parameter.

    Accepts two formats:
      "W,S,E,N"   — same convention as download_sentinel5p.py
      "N/W/S/E"   — CDS native format
    """
    try:
        if "/" in raw:
            north, west, south, east = (float(x.strip()) for x in raw.split("/"))
        else:
            west, south, east, north = (float(x.strip()) for x in raw.split(","))
        if not (-180 <= west < east <= 180) or not (-90 <= south < north <= 90):
            raise ValueError("Coordinates out of range.")
        return [north, west, south, east]
    except ValueError as exc:
        log.error("Invalid --bbox '%s': %s", raw, exc)
        sys.exit(1)


# ── CDS download ──────────────────────────────────────────────────────────────

def _build_cds_client(api_url: str, api_key: str):  # type: ignore[return]
    """
    Construct a cdsapi.Client configured from explicit credentials rather than
    the ~/.cdsapirc file, so the script is fully driven by env vars.

    cdsapi >=0.7 delegates to ecmwf-datastores-client, which reads credentials
    from ECMWF_DATASTORES_URL / ECMWF_DATASTORES_KEY environment variables (not
    the url= / key= constructor arguments).  We set those here so the caller's
    CDS_API_URL / CDS_API_KEY values are honoured without requiring a ~/.cdsapirc.
    """
    try:
        import cdsapi  # type: ignore[import]
    except ImportError:
        log.error("cdsapi is not installed. Run: pip install cdsapi")
        sys.exit(1)

    import os as _os
    # Set all env var names the various cdsapi/ecmwf-datastores layers read.
    # Use direct assignment (not setdefault) so our values always win.
    _os.environ["CDSAPI_URL"] = api_url
    _os.environ["CDSAPI_KEY"] = api_key
    _os.environ["ECMWF_DATASTORES_URL"] = api_url
    _os.environ["ECMWF_DATASTORES_KEY"] = api_key

    # Also pass explicitly to the constructor for older cdsapi builds.
    return cdsapi.Client(url=api_url, key=api_key, quiet=True)


def _download_month(
    client,  # cdsapi.Client
    variables: list[str],
    year_month: str,
    days: list[str],
    area: list[float],
    output_format: str,
    out_dir: Path,
) -> Path:
    """
    Submit one CDS retrieve request for a single month slice and wait for the
    result.  Returns the path to the saved file.
    """
    year, month = year_month.split("-")
    ext = "nc" if output_format == "netcdf" else "grib"
    safe_vars = "-".join(v.replace("_", "") for v in variables[:3])
    filename = f"era5_{year}{month}_{safe_vars}.{ext}"
    out_path = out_dir / filename

    if out_path.exists():
        log.info("File already exists, skipping: %s", out_path)
        return out_path

    request = {
        "product_type": "reanalysis",
        "variable": variables,
        "year": year,
        "month": month,
        "day": days,
        "time": DEFAULT_TIMES,
        "area": area,
        "format": output_format,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info(
                "Requesting %s/%s — %d variable(s), %d day(s) [attempt %d/%d] …",
                year, month, len(variables), len(days), attempt, MAX_RETRIES,
            )
            client.retrieve(CDS_DATASET, request, str(out_path))
            log.info("Saved: %s", out_path)
            return out_path
        except Exception as exc:  # noqa: BLE001
            wait = RETRY_BASE_SLEEP * (2 ** (attempt - 1))
            log.warning(
                "CDS retrieve attempt %d/%d failed: %s. Retrying in %d s …",
                attempt, MAX_RETRIES, exc, wait,
            )
            time.sleep(wait)

    raise RuntimeError(
        f"CDS retrieve failed for {year_month} after {MAX_RETRIES} attempts."
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download ERA5 reanalysis data from the ECMWF CDS API."
    )
    parser.add_argument(
        "--start-date",
        required=True,
        metavar="YYYY-MM-DD",
        help="Start of the time range (inclusive).",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        metavar="YYYY-MM-DD",
        help="End of the time range (inclusive).",
    )
    parser.add_argument(
        "--variables",
        default=(
            "2m_temperature,"
            "10m_u_component_of_wind,"
            "10m_v_component_of_wind,"
            "boundary_layer_height"
        ),
        metavar="VAR1,VAR2,…",
        help=(
            "Comma-separated ERA5 variable names. "
            f"Supported: {', '.join(SUPPORTED_VARIABLES)}."
        ),
    )
    parser.add_argument(
        "--bbox",
        default=None,
        metavar="W,S,E,N or N/W/S/E",
        help=(
            "Spatial subset bounding box. "
            "Format: 'W,S,E,N' or 'N/W/S/E'. "
            "Omit for global coverage."
        ),
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        default="netcdf",
        choices=["netcdf", "grib"],
        help="Output file format (default: netcdf).",
    )
    parser.add_argument(
        "--out-dir",
        default="data/raw/era5",
        metavar="DIR",
        help="Output directory (default: data/raw/era5).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the request parameters without submitting to CDS.",
    )
    return parser.parse_args()


def _validate_date(value: str, name: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")  # noqa: DTZ007 — date-only input, no tz context needed
    except ValueError:
        log.error("%s '%s' is not a valid YYYY-MM-DD date.", name, value)
        sys.exit(1)


def _validate_variables(raw: str) -> list[str]:
    requested = [v.strip() for v in raw.split(",") if v.strip()]
    unknown = [v for v in requested if v not in SUPPORTED_VARIABLES]
    if unknown:
        log.warning(
            "Unknown variable(s) — will be sent to CDS anyway (may fail): %s",
            ", ".join(unknown),
        )
    if not requested:
        log.error("No variables specified.")
        sys.exit(1)
    return requested


def main() -> None:
    load_dotenv()
    args = _parse_args()

    start_dt = _validate_date(args.start_date, "--start-date")
    end_dt = _validate_date(args.end_date, "--end-date")
    if start_dt > end_dt:
        log.error("--start-date must not be after --end-date.")
        sys.exit(1)

    variables = _validate_variables(args.variables)
    area = _parse_bbox_cds(args.bbox) if args.bbox else None

    api_url = os.environ.get("CDS_API_URL", DEFAULT_CDS_URL)
    api_key = os.environ.get("CDS_API_KEY", "")
    if not api_key:
        log.error(
            "CDS_API_KEY must be set in the environment."
        )
        sys.exit(1)

    # Strip legacy "UID:token" prefix — the new CDS API accepts only the bare token.
    if ":" in api_key and not api_key.startswith("http"):
        api_key = api_key.split(":", 1)[1]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    month_slices = _date_range_months(start_dt, end_dt)
    log.info(
        "Planning %d monthly request(s) for variables: %s",
        len(month_slices), ", ".join(variables),
    )

    if args.dry_run:
        for year_month, days in month_slices:
            log.info(
                "  DRY RUN — %s: %d day(s)  area=%s  format=%s",
                year_month, len(days), area, args.output_format,
            )
        return

    client = _build_cds_client(api_url, api_key)
    failed: list[str] = []

    for year_month, days in month_slices:
        try:
            _download_month(
                client=client,
                variables=variables,
                year_month=year_month,
                days=days,
                area=area,
                output_format=args.output_format,
                out_dir=out_dir,
            )
        except RuntimeError as exc:
            log.error("Failed: %s", exc)
            failed.append(year_month)

    log.info(
        "ERA5 download complete. Success: %d  Failed: %d",
        len(month_slices) - len(failed),
        len(failed),
    )
    if failed:
        log.warning("Failed months: %s", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
