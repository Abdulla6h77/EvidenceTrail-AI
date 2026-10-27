from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Environment-backed configuration with safe demo defaults."""

    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), str(PROJECT_ROOT / "backend" / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "EvidenceTrail AI"
    app_env: str = Field(default="demo", pattern="^(demo|live)$")
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_path: str = str(PROJECT_ROOT / "data" / "evidencetrail.db")
    frontend_origin: str = "http://localhost:3000"

    zetaris_base_url: str | None = None
    zetaris_api_key: str | None = None
    zetaris_org_id: str | None = None
    zetaris_timeout_seconds: float = Field(default=20, ge=1, le=120)
    zetaris_page_limit: int = Field(default=100, ge=1, le=100)
    zetaris_dataset_mode: str = Field(default="registered", pattern="^(registered|inline_synthetic)$")

    model_base_url: str = "https://integrate.api.nvidia.com/v1"
    model_api_key: str | None = None
    nemotron_model: str | None = None
    model_timeout_seconds: float = Field(default=45, ge=1, le=180)

    meterless_hmem_enabled: bool = False
    meterless_hmem_node_binary: str = "node"
    meterless_hmem_base_url: str | None = None
    meterless_hmem_api_key: str | None = None

    max_query_rows: int = Field(default=500, ge=1, le=5000)
    query_timeout_seconds: float = Field(default=5, ge=0.1, le=30)

    @property
    def database_file(self) -> Path:
        path = Path(self.database_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
