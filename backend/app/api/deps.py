"""
backend/app/api/deps.py
─────────────────────────────────────────────────────────────────────────────
FastAPI dependency functions shared across route modules.

API key guard:
  When DEMO_API_KEY is set (non-empty), callers must pass an X-Api-Key header
  with the matching value on mutating endpoints.  Read-only endpoints are left
  open intentionally so judges can browse the dashboard without credentials.
  When DEMO_API_KEY is empty (the dev default), the guard is a no-op so local
  development requires no extra setup.
"""

from fastapi import Header, HTTPException

from app.core.config import settings


def require_api_key(x_api_key: str = Header(default="")) -> None:
    """Raise 401 if a DEMO_API_KEY is configured and the caller did not supply it."""
    if settings.demo_api_key and x_api_key != settings.demo_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
