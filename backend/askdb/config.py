"""Runtime configuration, read from environment variables (or a .env file)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASKDB_", env_file=".env", extra="ignore")

    # Read without the ASKDB_ prefix so the standard variable works. If unset,
    # the Anthropic SDK falls back to its own credential resolution.
    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")

    # SQLAlchemy URL. Defaults to the bundled Chinook sample database.
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'chinook.sqlite'}"
    # Which generator answers by default: a free hosted model (the default, so
    # testing costs nothing), Claude, or an open model served locally. "auto" uses
    # Claude when Anthropic credentials are set, otherwise the free model.
    provider: Literal["auto", "claude", "free", "local"] = "free"

    model: str = "claude-opus-5-5"
    effort: str = "medium"

    # Free hosted model (provider="free"): any OpenAI-compatible chat API.
    # Default is Google Gemini's free tier (key: https://aistudio.google.com/apikey).
    free_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    free_api_key: SecretStr | None = None
    free_model: str = "gemini-flash-latest"
    free_timeout_s: float = 120.0

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

    # Uploaded databases (SQLite files or CSVs). Each upload belongs to the browser
    # that made it (a random id kept in localStorage, not an account), so other
    # visitors can't see, query, or delete it.
    allow_uploads: bool = True
    upload_dir: Path = BACKEND_DIR / "data" / "uploads"
    max_upload_mb: int = 50
    max_uploads: int = 20  # per browser
    max_total_uploads: int = 200  # across everyone: caps disk use on a public server

    @field_validator("anthropic_api_key", "free_api_key", mode="before")
    @classmethod
    def _blank_is_unset(cls, v: object) -> object:
        # `.env.example` ships with empty `KEY=` lines; treat those as not set.
        return None if isinstance(v, str) and not v.strip() else v


@lru_cache
def get_settings() -> Settings:
    return Settings()
