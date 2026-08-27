"""Backend package bootstrap.

Both the local development command (run from ``backend/``) and the Docker
image need to import the repository-level ``shared`` package.  Find that
repository root rather than relying on a caller-specific ``PYTHONPATH``.
"""

from __future__ import annotations

import sys
from pathlib import Path


for _parent in Path(__file__).resolve().parents:
    if (_parent / "shared").is_dir():
        sys.path.insert(0, str(_parent))
        break
