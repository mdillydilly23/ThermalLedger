"""
ML service config.
ADR-002: DATA_SOURCE — local|remote satellite data.
ADR-006: GRANITE_MODE — cached|live Granite calls.
"""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class MLSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ADR-002
    data_source: Literal["local", "remote"] = "local"
    data_dir: Path = Path("../data")

    # ADR-006
    granite_mode: Literal["cached", "live"] = "cached"
    # Relative to ml/ for native development and /app for the container.
    granite_cache_dir: Path = Path("cache/granite")
    reports_cache_dir: Path = Path("cache/reports")

    # IBM watsonx.ai
    watsonx_api_key: str = ""
    watsonx_project_id: str = ""
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"
    granite_model_id: str = "ibm/granite-13b-instruct-v2"

    ml_host: str = "0.0.0.0"
    ml_port: int = 8001


settings = MLSettings()
