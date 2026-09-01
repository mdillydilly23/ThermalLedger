#!/usr/bin/env python3
"""
scripts/download_sentinel5p.py
───────────────────────────────
Download Sentinel-5P (TROPOMI) products from the Copernicus Data Space Ecosystem
(CDSE) OData/STAC API.

Usage
-----
python scripts/download_sentinel5p.py \\
    --start-date 2024-01-01 \\
    --end-date   2024-01-31 \\
    --bbox="-5.0,35.0,40.0,72.0" \\
    --product    L2__CH4___ \\
    --out-dir    data/raw/sentinel5p

Note: use ``--bbox=VALUE`` (equals sign) when the bbox starts with a negative
number, otherwise the shell passes it as an unknown flag.

Environment variables (set in .env or shell)
--------------------------------------------
COPERNICUS_USERNAME   – CDSE account username
COPERNICUS_PASSWORD   – CDSE account password
COPERNICUS_CLIENT_ID  – OAuth client ID (default: cdse-public)

The script supports resumable downloads: if a file with the expected name already
exists in the output directory its byte-size is compared to the server's
Content-Length header.  Partial files are continued with HTTP Range requests.
A per-file retry loop with exponential back-off handles transient network errors.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("sentinel5p.downloader")

# ── Constants ────────────────────────────────────────────────────────────────
CDSE_TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu"
    "/auth/realms/CDSE/protocol/openid-connect/token"
)
CDSE_CATALOG_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
CDSE_DOWNLOAD_BASE = "https://download.dataspace.copernicus.eu/odata/v1/Products"

# Products the downloader accepts (TROPOMI Level-2)
VALID_PRODUCT_TYPES = [
    "L2__NO2___",
    "L2__CO____",
    "L2__CH4___",
    "L2__O3____",
    "L2__SO2___",
    "L2__HCHO__",
    "L2__AER_AI",
    "L2__CLOUD_",
]

MAX_RETRIES = 5
CHUNK_SIZE = 1 << 20  # 1 MiB
RATE_LIMIT_SLEEP = 2.0  # seconds between page requests


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _fetch_access_token(username: str, password: str, client_id: str) -> str:
    """Exchange CDSE credentials for a short-lived OAuth 2.0 access token."""
    log.info("Authenticating with Copernicus Data Space Ecosystem …")
    resp = requests.post(
        CDSE_TOKEN_URL,
        data={
            "grant_type": "password",
            "username": username,
            "password": password,
            "client_id": client_id,
        },
        timeout=30,
    )
    resp.raise_for_status()
    token: str = resp.json()["access_token"]
    log.info("Access token obtained.")
    return token


# ── Catalog search ────────────────────────────────────────────────────────────

def _build_filter(
    product_type: str,
    start_date: str,
    end_date: str,
    bbox: tuple[float, float, float, float],
) -> str:
    """Build an OData $filter expression for CDSE catalog search."""
    west, south, east, north = bbox
    footprint = (
        f"OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(("
        f"{west} {south},{east} {south},{east} {north},{west} {north},{west} {south}"
        f"))')"
    )
    return (
        f"Collection/Name eq 'SENTINEL-5P'"
        f" and Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType'"
        f" and att/OData.CSC.StringAttribute/Value eq '{product_type}')"
        f" and ContentDate/Start ge {start_date}T00:00:00.000Z"
        f" and ContentDate/Start le {end_date}T23:59:59.999Z"
        f" and {footprint}"
    )


def search_products(
    product_type: str,
    start_date: str,
    end_date: str,
    bbox: tuple[float, float, float, float],
) -> list[dict[str, Any]]:
    """Page through the CDSE OData catalog and return all matching product records."""
    products: list[dict[str, Any]] = []
    odata_filter = _build_filter(product_type, start_date, end_date, bbox)
    url = CDSE_CATALOG_URL
    params: dict[str, Any] = {
        "$filter": odata_filter,
        "$orderby": "ContentDate/Start asc",
        "$top": 100,
        "$expand": "Attributes",
    }

    page = 0
    while url:
        page += 1
        log.info("Fetching catalog page %d …", page)
        resp = requests.get(url, params=params if page == 1 else None, timeout=60)
        if resp.status_code == 429:
            log.warning("Rate-limited by CDSE catalog (429). Sleeping 30 s …")
            time.sleep(30)
            continue
        resp.raise_for_status()
        body = resp.json()
        batch = body.get("value", [])
        products.extend(batch)
        log.info("  … %d products retrieved so far.", len(products))
        # OData server-side paging
        url = body.get("@odata.nextLink")
        params = {}
        time.sleep(RATE_LIMIT_SLEEP)

    log.info("Catalog search complete — %d products found.", len(products))
    return products


# ── Download helpers ──────────────────────────────────────────────────────────

def _download_product(
    product: dict[str, Any],
    out_dir: Path,
    session: requests.Session,
) -> Path:
    """
    Download a single product with resume and retry support.

    Parameters
    ----------
    product:  OData product record from the catalog.
    out_dir:  Directory where files are saved.
    session:  Authenticated requests.Session.

    Returns
    -------
    Path to the saved file.
    """
    product_id: str = product["Id"]
    product_name: str = product["Name"]
    download_url = f"{CDSE_DOWNLOAD_BASE}({product_id})/$value"
    out_path = out_dir / product_name

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Determine resume offset
            headers: dict[str, str] = {}
            existing_bytes = out_path.stat().st_size if out_path.exists() else 0
            if existing_bytes:
                headers["Range"] = f"bytes={existing_bytes}-"
                log.info(
                    "Resuming %s from byte %d …", product_name, existing_bytes
                )
            else:
                log.info("Downloading %s (attempt %d/%d) …", product_name, attempt, MAX_RETRIES)

            with session.get(
                download_url,
                headers=headers,
                stream=True,
                timeout=120,
            ) as resp:
                if resp.status_code == 429:
                    wait = 60 * attempt
                    log.warning("Rate-limited (429). Waiting %d s before retry …", wait)
                    time.sleep(wait)
                    continue
                if resp.status_code == 416:
                    # Range not satisfiable — file already complete
                    log.info("%s already complete (416 Range Not Satisfiable).", product_name)
                    return out_path
                resp.raise_for_status()

                mode = "ab" if existing_bytes and resp.status_code == 206 else "wb"
                with open(out_path, mode) as fh:
                    for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            fh.write(chunk)

            log.info("Saved: %s", out_path)
            return out_path

        except (requests.RequestException, OSError) as exc:
            wait = 2**attempt
            log.warning(
                "Attempt %d/%d failed for %s: %s. Retrying in %d s …",
                attempt, MAX_RETRIES, product_name, exc, wait,
            )
            time.sleep(wait)

    raise RuntimeError(
        f"Failed to download {product_name} after {MAX_RETRIES} attempts."
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Sentinel-5P TROPOMI products from Copernicus Data Space."
    )
    parser.add_argument(
        "--start-date",
        required=True,
        metavar="YYYY-MM-DD",
        help="Observation start date (inclusive).",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        metavar="YYYY-MM-DD",
        help="Observation end date (inclusive).",
    )
    parser.add_argument(
        "--bbox",
        required=True,
        metavar="W,S,E,N",
        help="Bounding box as comma-separated floats: west,south,east,north.",
    )
    parser.add_argument(
        "--product",
        default="L2__CH4___",
        choices=VALID_PRODUCT_TYPES,
        metavar="PRODUCT_TYPE",
        help=(
            f"TROPOMI product type. Choices: {', '.join(VALID_PRODUCT_TYPES)}. "
            "Default: L2__CH4___."
        ),
    )
    parser.add_argument(
        "--out-dir",
        default="data/raw/sentinel5p",
        metavar="DIR",
        help="Output directory for downloaded files (default: data/raw/sentinel5p).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List matching products without downloading.",
    )
    return parser.parse_args()


def _validate_date(value: str, name: str) -> None:
    try:
        datetime.strptime(value, "%Y-%m-%d")  # noqa: DTZ007 — date-only input, no tz context needed
    except ValueError:
        log.error("%s '%s' is not a valid YYYY-MM-DD date.", name, value)
        sys.exit(1)


def _parse_bbox(raw: str) -> tuple[float, float, float, float]:
    try:
        parts = [float(x.strip()) for x in raw.split(",")]
        if len(parts) != 4:
            raise ValueError("Expected exactly 4 values.")
        west, south, east, north = parts
        if not (-180 <= west < east <= 180) or not (-90 <= south < north <= 90):
            raise ValueError("Coordinates out of range.")
        return west, south, east, north
    except ValueError as exc:
        log.error("Invalid --bbox '%s': %s", raw, exc)
        sys.exit(1)


def main() -> None:
    load_dotenv()
    args = _parse_args()

    _validate_date(args.start_date, "--start-date")
    _validate_date(args.end_date, "--end-date")
    bbox = _parse_bbox(args.bbox)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Search catalog (public — no credentials required)
    products = search_products(args.product, args.start_date, args.end_date, bbox)
    if not products:
        log.info("No products matched the query. Exiting.")
        return

    if args.dry_run:
        log.info("Dry-run — matched products:")
        for p in products:
            log.info("  %s  (%s)", p["Name"], p.get("ContentDate", {}).get("Start", "?"))
        return

    # Credentials are only required for the actual download
    username = os.environ.get("COPERNICUS_USERNAME", "")
    password = os.environ.get("COPERNICUS_PASSWORD", "")
    client_id = os.environ.get("COPERNICUS_CLIENT_ID", "cdse-public")

    if not username or not password:
        log.error(
            "COPERNICUS_USERNAME and COPERNICUS_PASSWORD must be set in the environment."
        )
        sys.exit(1)

    # Authenticate and download
    access_token = _fetch_access_token(username, password, client_id)
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {access_token}"})

    failed: list[str] = []
    for idx, product in enumerate(products, start=1):
        log.info("[%d/%d] Processing %s", idx, len(products), product["Name"])
        try:
            _download_product(product, out_dir, session)
        except RuntimeError as exc:
            log.error("Skipping product after exhausted retries: %s", exc)
            failed.append(product["Name"])

    log.info(
        "Download complete. Success: %d  Failed: %d",
        len(products) - len(failed),
        len(failed),
    )
    if failed:
        log.warning("Failed products:\n  %s", "\n  ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
