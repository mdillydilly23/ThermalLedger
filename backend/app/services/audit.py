"""Audit and governance fallback helpers for the live prototype.

OpenPages and Hyperledger Fabric are integration points, but the presentation
prototype needs an always-available audit trail.  These helpers write append-only
JSONL records under data/audit/ and return explicit local-fallback identifiers.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import settings


def audit_mode() -> str:
    """Return the active audit mode label exposed to the UI."""
    # The service boundary is ready for a Fabric client, but this prototype
    # implementation intentionally uses the local fallback until that client is
    # installed and tested.
    return "local_audit_fallback"


def anchor_payload(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a deterministic local anchor record for a score or report payload."""
    canonical = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    anchor_id = f"local_sha256:{digest}"
    record = {
        "anchor_id": anchor_id,
        "kind": kind,
        "mode": audit_mode(),
        "created_at": _utc_now(),
        "payload_sha256": digest,
        "payload": payload,
    }
    _append_jsonl(settings.audit_dir / "anchors.jsonl", record)
    return record


def create_case(facility_id: str, severity: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Write a local governance case when live OpenPages is unavailable."""
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    case_id = f"local_case:{facility_id}:{digest[:12]}"
    record = {
        "case_id": case_id,
        "facility_id": facility_id,
        "severity": severity,
        "mode": "local_openpages_fallback",
        "created_at": _utc_now(),
        "payload": payload,
    }
    _append_jsonl(settings.audit_dir / "cases.jsonl", record)
    return record


def latest_run() -> dict[str, Any] | None:
    """Return the latest verification run summary written by the worker."""
    return _last_jsonl(settings.data_dir / "processed" / "verification_runs.jsonl")


def record_run(summary: dict[str, Any]) -> None:
    """Append a verification run summary."""
    _append_jsonl(settings.data_dir / "processed" / "verification_runs.jsonl", summary)


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True, default=str)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _last_jsonl(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    last_line = ""
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                last_line = line
    if not last_line:
        return None
    return json.loads(last_line)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
