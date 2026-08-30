"""
Central config — reads from environment / .env file.
ADR-002: DATA_SOURCE controls local vs remote data routing.
ADR-006: GRANITE_MODE controls cached vs live Granite calls (ML service reads its own copy).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # CORS — stored internally as a raw string so pydantic-settings never
    # attempts JSON-decoding it.  _parse_allowed_origins converts it to a
    # list[str] after all fields are populated.
    # Accepted env formats:
    #   ALLOWED_ORIGINS=http://localhost:5173
    #   ALLOWED_ORIGINS=http://localhost:5173,https://my-app.example.com
    #   ALLOWED_ORIGINS=["http://localhost:5173"]
    allowed_origins: str = "http://localhost:5173"

    @model_validator(mode="after")
    def _parse_allowed_origins(self) -> "Settings":
        """Convert allowed_origins from env string to a list[str]."""
        raw = self.allowed_origins
        if isinstance(raw, list):
            # Already a list — nothing to do (e.g. programmatic construction).
            return self
        stripped = raw.strip()
        if not stripped:
            object.__setattr__(self, "allowed_origins", [])
            return self
        if stripped.startswith("["):
            object.__setattr__(self, "allowed_origins", json.loads(stripped))
        else:
            object.__setattr__(
                self,
                "allowed_origins",
                [o.strip() for o in stripped.split(",") if o.strip()],
            )
        return self

    # Demo API key — set to a non-empty value to guard mutating endpoints.
    # Use DEMO_API_KEY=thermalledger-demo in production .env deployments.
    demo_api_key: str = ""

    # ADR-002
    data_source: Literal["local", "remote"] = "local"
    data_dir: Path = Path("../data")
    granite_mode: Literal["cached", "live"] = "cached"
    reports_cache_dir: Path = Path("../ml/cache/reports")
    uploads_dir: Path = Path("../data/uploads/esg")
    audit_dir: Path = Path("../data/audit")

    # IBM watsonx.ai
    watsonx_api_key: str = ""
    watsonx_project_id: str = ""
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"

    # IBM watsonx.data
    watsonxdata_host: str = ""
    watsonxdata_port: int = 443
    watsonxdata_access_token: str = ""

    # IBM EIS
    eis_api_key: str = ""
    eis_base_url: str = "https://api.ibm.com/geospatial/run/na/core/v3"

    # IBM OpenPages
    openpages_base_url: str = ""
    openpages_api_key: str = ""

    # Hyperledger Fabric
    fabric_gateway_url: str = ""
    fabric_channel: str = "thermalledger"
    fabric_chaincode: str = "evs-anchor"
    fabric_identity_path: Path = Path("../infra/fabric-identity.json")

    # Service URLs
    ml_service_url: str = "http://ml:8001"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000


settings = Settings()
