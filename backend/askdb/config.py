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
    provider: Literal["auto", "claude", "free", "groq", "openrouter", "openai", "local"] = "free"

    model: str = "claude-opus-5-5"
    effort: str = "medium"
    # Claude models visitors may pick when the server's key pays. With their own
    # key, users can pick any model in askdb.providers.CLAUDE_MODELS.
    claude_models: list[str] = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5"]

    # Free hosted model (provider="free"): any OpenAI-compatible chat API.
    # Default is Google Gemini's free tier (key: https://aistudio.google.com/apikey).
    free_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    free_api_key: SecretStr | None = None
    free_model: str = "gemini-flash-latest"
    free_timeout_s: float = 120.0
    # Models visitors may pick with the server's key (empty = only the default).
    # With their own key, users can pick any model the provider lists for it.
    free_models: list[str] = []

    # More OpenAI-compatible providers, each with its own key and model choice.
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"
    groq_models: list[str] = []

    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: SecretStr | None = None
    openrouter_model: str = "openrouter/auto"
    openrouter_models: list[str] = []

    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5-mini"
    openai_models: list[str] = []

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

    # Live databases (Postgres, MySQL) people connect from the UI with a connection
    # string. Like uploads, each belongs to the browser that added it and counts
    # toward max_uploads. The URL (with its password) is kept on the server in
    # upload_dir, readable only by the server's user. Ask people to use a
    # read-only database user; AskDB also opens every connection read-only.
    allow_connections: bool = True
    # Set false on a public server so visitors can't reach localhost or private
    # network addresses (the server's own network) through a connection string.
    allow_private_hosts: bool = True

    # Embedding-based schema linking for large schemas (more than 15 tables).
    # Off unless a model is set; uses any OpenAI-compatible /embeddings API. The
    # base URL and key default to the free provider's (Gemini), e.g.
    # ASKDB_EMBEDDING_MODEL=gemini-embedding-001. Keyword ranking is always used too.
    embedding_model: str | None = None
    embedding_base_url: str | None = None
    embedding_api_key: SecretStr | None = None

    # Results. The first row_limit rows come with the answer; "Load more" pages
    # through the rest max_page_rows at a time; CSV export streams up to
    # export_row_limit rows.
    max_page_rows: int = 1000
    export_row_limit: int = 100_000
    # A plain-language sentence under each answer: "model" asks the model that
    # wrote the SQL (one extra call), "simple" uses a template, "off" shows none.
    summaries: Literal["model", "simple", "off"] = "model"

    # Saved answers (history that follows the browser's id) and 👍/👎 feedback.
    store_path: Path = BACKEND_DIR / "data" / "askdb.sqlite"
    save_history: bool = True
    max_saved_answers: int = 500  # per browser
    # Questions the same browser marked correct (or corrected) for the same
    # database are added to the prompt as examples, the most similar first.
    feedback_examples: int = 3

    # Eval results (eval/run_eval.py --out) label measured models in the model menu.
    eval_results_dir: Path = BACKEND_DIR / "eval" / "results"

    @field_validator(
        "anthropic_api_key",
        "free_api_key",
        "groq_api_key",
        "openrouter_api_key",
        "openai_api_key",
        "embedding_api_key",
        mode="before",
    )
    @classmethod
    def _blank_is_unset(cls, v: object) -> object:
        # `.env.example` ships with empty `KEY=` lines; treat those as not set.
        return None if isinstance(v, str) and not v.strip() else v


@lru_cache
def get_settings() -> Settings:
    return Settings()
