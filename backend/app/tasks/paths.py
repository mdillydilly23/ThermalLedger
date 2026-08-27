"""Resolve repository assets in both the source tree and Docker image."""

from __future__ import annotations

from pathlib import Path


def script_path(name: str) -> Path:
    """Return a bootstrap script whether the task runs locally or in Docker."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "scripts" / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Unable to locate scripts/{name}")
