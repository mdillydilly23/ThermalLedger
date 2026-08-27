"""Test bootstrap for the backend service."""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DATA_DIR", str(ROOT / "data"))
os.environ.setdefault("GRANITE_MODE", "cached")
