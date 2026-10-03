"""Wire the stages together behind one object the CLI, API, and eval share."""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from typing import Literal

import anthropic
from sqlalchemy import Engine

from askdb.config import Settings, get_settings
from askdb.db import make_engine
from askdb.execute import Answer, EventHandler, answer, run_sql
from askdb.generate import (
    ClaudeGenerator,
    GenerationError,
    SQLGenerator,
    Turn,
    build_system_prompt,
)
from askdb.hosted import HostedGenerator
from askdb.local import LocalGenerator
from askdb.prompts import FEW_SHOT_EXAMPLES
from askdb.schema import Schema, introspect, link_tables

MISSING_ANTHROPIC_KEY = (
    "No Anthropic key. Add yours under API keys (the key button at the top of the page), "
    "set ANTHROPIC_API_KEY on the server, or switch to the Free model."
)

Provider = Literal["claude", "free", "local"]


@dataclass
class AskDB:
    settings: Settings
    engine: Engine
    schema: Schema
    # Few-shot examples written for this database (none for uploads).
    examples: list[tuple[str, str]] = field(default_factory=lambda: list(FEW_SHOT_EXAMPLES))
    # "Today" for relative dates. None means the real current date.
    fixed_date: str | None = None
    _client: anthropic.Anthropic | None = field(default=None, repr=False)

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> AskDB:
        """The configured database (the bundled Chinook sample by default)."""
        settings = settings or get_settings()
        engine = make_engine(settings.database_url, settings.statement_timeout_s)
        return cls(
            settings=settings,
            engine=engine,
            schema=introspect(engine),
            fixed_date=settings.reference_date,
        )

    @classmethod
    def for_sqlite_file(
        cls, path: str, settings: Settings | None = None, client: anthropic.Anthropic | None = None
    ) -> AskDB:
        """An uploaded SQLite file: no schema-specific examples, real dates."""
        settings = settings or get_settings()
        engine = make_engine(f"sqlite:///{path}", settings.statement_timeout_s)
        return cls(
            settings=settings,
            engine=engine,
            schema=introspect(engine),
            examples=[],
            fixed_date=None,
            _client=client,
        )

    @property
    def reference_date(self) -> str:
        return self.fixed_date or dt.date.today().isoformat()

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            key = self.settings.anthropic_api_key
            api_key = key.get_secret_value() if key else None
            self._client = (
                anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
            )
        return self._client

    @property
    def has_anthropic_credentials(self) -> bool:
        return bool(
            self.settings.anthropic_api_key
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        )

    @property
    def configured(self) -> dict[str, bool]:
        """Which providers have what they need (the local server isn't checked)."""
        return {
            "claude": self.has_anthropic_credentials,
            "free": self.settings.free_api_key is not None,
            "local": True,
        }

    @property
    def default_provider(self) -> Provider:
        p = self.settings.provider
        if p != "auto":
            return p
        return "claude" if self.has_anthropic_credentials else "free"

    def model_name(self, provider: Provider | None = None) -> str:
        provider = provider or self.default_provider
        return {
            "claude": self.settings.model,
            "free": self.settings.free_model,
            "local": self.settings.local_model,
        }[provider]

    def generator_for(
        self,
        question: str,
        provider: Provider | None = None,
        context: list[Turn] | None = None,
        api_key: str | None = None,
    ) -> SQLGenerator:
        """The generator for a provider. `api_key` is the user's own key for that
        provider (from the browser); it takes precedence over the server's key."""
        provider = provider or self.default_provider
        # Link on the whole conversation so follow-ups keep the tables they build on.
        linking_text = " ".join([*(t.question for t in context or []), question])
        tables = link_tables(self.schema, linking_text)
        if provider == "local":
            return LocalGenerator(
                dialect=self.schema.dialect,
                schema_ddl=self.schema.ddl(tables),
                model=self.settings.local_model,
                base_url=self.settings.local_base_url,
                api=self.settings.local_api,
                reference_date=self.reference_date,
                timeout_s=self.settings.local_timeout_s,
                context=context,
            )
        system = build_system_prompt(
            dialect=self.schema.dialect,
            schema_ddl=self.schema.ddl(tables),
            row_limit=self.settings.row_limit,
            reference_date=self.reference_date,
            examples=self.examples,
        )
        if provider == "free":
            key = self.settings.free_api_key
            return HostedGenerator(
                system,
                model=self.settings.free_model,
                base_url=self.settings.free_base_url,
                api_key=api_key or (key.get_secret_value() if key else None),
                context=context,
                timeout_s=self.settings.free_timeout_s,
            )
        if not api_key and not self.has_anthropic_credentials:
            raise GenerationError(MISSING_ANTHROPIC_KEY)
        return ClaudeGenerator(
            system,
            model=self.settings.model,
            effort=self.settings.effort,
            client=anthropic.Anthropic(api_key=api_key) if api_key else self.client,
            context=context,
        )

    def ask(
        self,
        question: str,
        generator: SQLGenerator | None = None,
        provider: Provider | None = None,
        context: list[Turn] | None = None,
        on_event: EventHandler | None = None,
        api_key: str | None = None,
    ) -> Answer:
        return answer(
            question,
            generator or self.generator_for(question, provider, context, api_key),
            self.engine,
            self.schema.dialect,
            max_retries=self.settings.max_retries,
            row_limit=self.settings.row_limit,
            on_event=on_event,
        )

    def run(self, sql: str) -> Answer:
        return run_sql(sql, self.engine, self.schema.dialect, self.settings.row_limit)
