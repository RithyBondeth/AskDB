"""Runtime configuration, read from environment variables (or a .env file)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASKDB_", env_file=".env", extra="ignore")

    # Read without the ASKDB_ prefix so the standard variable works. If unset,
    # the Anthropic SDK falls back to its own credential resolution.
    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")

    # SQLAlchemy URL. Defaults to the bundled Chinook sample database.
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'chinook.sqlite'}"
    # Which generator answers by default: Claude, or an open model served locally.
    provider: Literal["claude", "local"] = "claude"

    model: str = "claude-opus-5-5"
    effort: str = "medium"

    # Open model (provider="local"). Defaults to Arctic-Text2SQL-R1-7B via Ollama.
    local_model: str = "hf.co/mradermacher/Arctic-Text2SQL-R1-7B-GGUF:Q4_K_M"
    local_base_url: str = "http://localhost:11434"
    local_api: Literal["ollama", "openai"] = "ollama"
    local_timeout_s: float = 600.0
    max_retries: int = 2
    row_limit: int = 100
    statement_timeout_s: float = 10.0
    # Relative dates ("last quarter") are resolved against this date. Chinook's
    # invoices end in Dec 2013, so "today" is pinned there by default.
    reference_date: str | None = "2013-12-31"
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
