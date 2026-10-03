"""Runtime configuration, read from environment variables (or a .env file)."""

from functools import lru_cache
from pathlib import Path

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
    model: str = "claude-opus-5-5"
    effort: str = "medium"
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
