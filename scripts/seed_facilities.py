#!/usr/bin/env python3
"""
scripts/seed_facilities.py
───────────────────────────
Seed the application database with initial facility registry data.

The script reads facility records from a structured source file (CSV or JSON),
validates each record, and upserts them into the `facilities` table via
SQLAlchemy — using INSERT … ON CONFLICT (facility_id) DO UPDATE so the operation
is safe to run repeatedly (idempotent).

Usage
-----
python scripts/seed_facilities.py \\
    --source  data/fixtures/registry.csv \\
    --format  csv

python scripts/seed_facilities.py \\
    --source  data/raw/facilities/registry.json \\
    --format  json \\
    --dry-run

Environment variables
---------------------
DATABASE_URL  – SQLAlchemy connection string, e.g.
                postgresql+psycopg2://user:pass@localhost:5432/thermalledger
                (falls back to a local SQLite file for development)

Source file schema (CSV header / JSON keys)
-------------------------------------------
facility_id       – required, str — unique registry identifier (EU ETS / GHGRP)
facility_name     – required, str
latitude          – required, float  (-90 … 90)
longitude         – required, float  (-180 … 180)
sector            – required, str    (e.g. "oil_gas", "coal", "agriculture")
country           – optional, str    (ISO-3166 alpha-2)
operator          – optional, str
capacity_mw       – optional, float
reported_ch4_kt   – optional, float  (kilotonnes/year from self-reporting)
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("seed_facilities")

# ── Fallback DB URL for local dev ─────────────────────────────────────────────
_DEFAULT_DB_URL = "sqlite:///./thermalledger_dev.db"

# ── Validation schema ─────────────────────────────────────────────────────────

class FacilityRecord(BaseModel):
    """Pydantic validation model for a raw facility row."""

    facility_id: str = Field(..., min_length=1)
    facility_name: str = Field(..., min_length=1)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    sector: str = Field(..., min_length=1)
    country: str | None = None
    operator: str | None = None
    capacity_mw: float | None = None
    reported_ch4_kt: float | None = None

    @field_validator("facility_id", mode="before")
    @classmethod
    def strip_whitespace(cls, v: Any) -> str:
        return str(v).strip()

    @field_validator("latitude", "longitude", "capacity_mw", "reported_ch4_kt", mode="before")
    @classmethod
    def coerce_numeric(cls, v: Any) -> float | None:
        if v is None or v == "":
            return None
        return float(v)


# ── Source file readers ───────────────────────────────────────────────────────

def _load_csv(path: Path) -> list[dict[str, Any]]:
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return [dict(row) for row in reader]


def _load_json(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "facilities" in data:
        return data["facilities"]
    raise ValueError(
        "JSON source must be a top-level array or an object with a 'facilities' key."
    )


# ── Database helpers ──────────────────────────────────────────────────────────

def _get_engine(db_url: str):
    """Create a SQLAlchemy engine, importing lazily to avoid hard dependency at import time."""
    try:
        from sqlalchemy import create_engine  # type: ignore[import]
    except ImportError:
        log.error("sqlalchemy is not installed. Run: pip install sqlalchemy")
        sys.exit(1)
    return create_engine(db_url, future=True)


def _ensure_table(engine) -> None:
    """Create the facilities table if it does not already exist."""
    from sqlalchemy import (  # type: ignore[import]
        Column,
        Float,
        MetaData,
        String,
        Table,
    )

    meta = MetaData()
    Table(
        "facilities",
        meta,
        Column("facility_id", String, primary_key=True),
        Column("facility_name", String, nullable=False),
        Column("latitude", Float, nullable=False),
        Column("longitude", Float, nullable=False),
        Column("sector", String, nullable=False),
        Column("country", String),
        Column("operator", String),
        Column("capacity_mw", Float),
        Column("reported_ch4_kt", Float),
        extend_existing=True,
    )
    meta.create_all(engine)
    log.info("Table 'facilities' is ready.")


def _upsert_batch(engine, records: list[FacilityRecord], batch_size: int = 500) -> int:
    """
    Upsert records using dialect-aware INSERT … ON CONFLICT logic.

    Returns the number of rows inserted or updated.
    """
    dialect = engine.dialect.name  # "postgresql" | "sqlite" | etc.
    rows_affected = 0

    with engine.begin() as conn:
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            if dialect == "postgresql":
                rows_affected += _upsert_postgres(conn, batch)
            elif dialect == "sqlite":
                rows_affected += _upsert_sqlite(conn, batch)
            else:
                # Generic fallback: delete + insert
                rows_affected += _upsert_generic(conn, batch)
            log.info(
                "Upserted batch %d-%d (%d records).",
                i + 1, min(i + batch_size, len(records)), len(batch),
            )

    return rows_affected


def _record_dict(r: FacilityRecord) -> dict[str, Any]:
    return r.model_dump()


def _upsert_postgres(conn, batch: list[FacilityRecord]) -> int:
    from sqlalchemy import text  # type: ignore[import]

    sql = text(
        """
        INSERT INTO facilities
            (facility_id, facility_name, latitude, longitude,
             sector, country, operator, capacity_mw, reported_ch4_kt)
        VALUES
            (:facility_id, :facility_name, :latitude, :longitude,
             :sector, :country, :operator, :capacity_mw, :reported_ch4_kt)
        ON CONFLICT (facility_id) DO UPDATE SET
            facility_name  = EXCLUDED.facility_name,
            latitude       = EXCLUDED.latitude,
            longitude      = EXCLUDED.longitude,
            sector         = EXCLUDED.sector,
            country        = EXCLUDED.country,
            operator       = EXCLUDED.operator,
            capacity_mw    = EXCLUDED.capacity_mw,
            reported_ch4_kt = EXCLUDED.reported_ch4_kt
        """
    )
    result = conn.execute(sql, [_record_dict(r) for r in batch])
    return result.rowcount if result.rowcount >= 0 else len(batch)


def _upsert_sqlite(conn, batch: list[FacilityRecord]) -> int:
    from sqlalchemy import text  # type: ignore[import]

    sql = text(
        """
        INSERT OR REPLACE INTO facilities
            (facility_id, facility_name, latitude, longitude,
             sector, country, operator, capacity_mw, reported_ch4_kt)
        VALUES
            (:facility_id, :facility_name, :latitude, :longitude,
             :sector, :country, :operator, :capacity_mw, :reported_ch4_kt)
        """
    )
    result = conn.execute(sql, [_record_dict(r) for r in batch])
    return result.rowcount if result.rowcount >= 0 else len(batch)


def _upsert_generic(conn, batch: list[FacilityRecord]) -> int:
    """Fallback: delete existing rows then insert, wrapped in the caller's transaction."""
    from sqlalchemy import text  # type: ignore[import]

    ids = [r.facility_id for r in batch]
    placeholders = ", ".join(f":id_{k}" for k in range(len(ids)))
    conn.execute(
        text(f"DELETE FROM facilities WHERE facility_id IN ({placeholders})"),
        {f"id_{k}": v for k, v in enumerate(ids)},
    )
    insert_sql = text(
        """
        INSERT INTO facilities
            (facility_id, facility_name, latitude, longitude,
             sector, country, operator, capacity_mw, reported_ch4_kt)
        VALUES
            (:facility_id, :facility_name, :latitude, :longitude,
             :sector, :country, :operator, :capacity_mw, :reported_ch4_kt)
        """
    )
    conn.execute(insert_sql, [_record_dict(r) for r in batch])
    return len(batch)


# ── Validation pass ───────────────────────────────────────────────────────────

def _validate_rows(
    raw_rows: list[dict[str, Any]],
) -> tuple[list[FacilityRecord], list[tuple[int, str]]]:
    """
    Validate every raw row against FacilityRecord.

    Returns
    -------
    valid   – list of validated FacilityRecord objects
    errors  – list of (row_number, error_message) for invalid rows
    """
    valid: list[FacilityRecord] = []
    errors: list[tuple[int, str]] = []

    for idx, row in enumerate(raw_rows, start=1):
        try:
            valid.append(FacilityRecord(**row))
        except ValidationError as exc:
            errors.append((idx, str(exc)))

    return valid, errors


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the facilities table from a CSV or JSON registry file."
    )
    parser.add_argument(
        "--source",
        default="data/fixtures/registry.csv",
        metavar="FILE",
        help="Path to the registry source file (default: data/fixtures/registry.csv).",
    )
    parser.add_argument(
        "--format",
        dest="file_format",
        default="csv",
        choices=["csv", "json"],
        help="Source file format (default: csv).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate rows and print summary without touching the database.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Abort if any row fails validation (default: skip invalid rows and continue).",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = _parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        log.error("Source file not found: %s", source_path)
        sys.exit(1)

    # Load raw rows
    log.info("Loading records from %s …", source_path)
    if args.file_format == "csv":
        raw_rows = _load_csv(source_path)
    else:
        raw_rows = _load_json(source_path)
    log.info("Read %d raw rows.", len(raw_rows))

    # Validate
    valid_records, errors = _validate_rows(raw_rows)
    if errors:
        for row_num, msg in errors:
            log.warning("Row %d validation error: %s", row_num, msg)
        if args.fail_fast:
            log.error("Aborting due to %d validation error(s) (--fail-fast).", len(errors))
            sys.exit(1)
        log.warning("Skipping %d invalid row(s). Continuing with %d valid.", len(errors), len(valid_records))
    else:
        log.info("All %d rows passed validation.", len(valid_records))

    if not valid_records:
        log.warning("No valid records to upsert. Exiting.")
        return

    if args.dry_run:
        log.info(
            "Dry-run — %d valid record(s) would be upserted. Sample:",
            len(valid_records),
        )
        for rec in valid_records[:5]:
            log.info("  %s", rec.model_dump())
        return

    # Database upsert
    db_url = os.environ.get("DATABASE_URL", _DEFAULT_DB_URL)
    log.info("Connecting to database: %s", db_url.split("@")[-1])  # omit credentials from log
    engine = _get_engine(db_url)
    _ensure_table(engine)

    affected = _upsert_batch(engine, valid_records)
    log.info(
        "Seeding complete. %d record(s) upserted from %d valid input rows.",
        affected, len(valid_records),
    )


if __name__ == "__main__":
    main()
