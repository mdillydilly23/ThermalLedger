"""
Central config — reads from environment / .env file.
ADR-002: DATA_SOURCE controls local vs remote data routing.
ADR-006: GRANITE_MODE controls cached vs live Granite calls (ML service reads its own copy).
"""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ADR-002
    data_source: Literal["local", "remote"] = "local"
    data_dir: Path = Path("../data")

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
