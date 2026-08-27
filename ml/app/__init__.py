"""ML package bootstrap; makes the repository-level shared contract importable."""

from __future__ import annotations

import sys
from pathlib import Path

for _parent in Path(__file__).resolve().parents:
    if (_parent / "shared").is_dir():
        sys.path.insert(0, str(_parent))
        break
