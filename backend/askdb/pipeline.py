"""Wire the stages together behind one object the CLI, API, and eval share."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import anthropic
from sqlalchemy import Engine

from askdb.config import Settings, get_settings
from askdb.db import make_engine
from askdb.execute import Answer, EventHandler, answer, run_sql
from askdb.generate import ClaudeGenerator, SQLGenerator, Turn, build_system_prompt
from askdb.local import LocalGenerator
from askdb.schema import Schema, introspect, link_tables

Provider = Literal["claude", "local"]


@dataclass
class AskDB:
    settings: Settings
    engine: Engine
    schema: Schema
    _client: anthropic.Anthropic | None = field(default=None, repr=False)

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> AskDB:
        settings = settings or get_settings()
        engine = make_engine(settings.database_url, settings.statement_timeout_s)
        return cls(settings=settings, engine=engine, schema=introspect(engine))

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            key = self.settings.anthropic_api_key
            api_key = key.get_secret_value() if key else None
            self._client = (
                anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
            )
        return self._client

    def model_name(self, provider: Provider | None = None) -> str:
        provider = provider or self.settings.provider
        return self.settings.local_model if provider == "local" else self.settings.model

    def generator_for(
        self,
        question: str,
        provider: Provider | None = None,
        context: list[Turn] | None = None,
    ) -> SQLGenerator:
        provider = provider or self.settings.provider
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
                reference_date=self.settings.reference_date,
                timeout_s=self.settings.local_timeout_s,
                context=context,
            )
        system = build_system_prompt(
            dialect=self.schema.dialect,
            schema_ddl=self.schema.ddl(tables),
            row_limit=self.settings.row_limit,
            reference_date=self.settings.reference_date,
        )
        return ClaudeGenerator(
            system,
            model=self.settings.model,
            effort=self.settings.effort,
            client=self.client,
            context=context,
        )

    def ask(
        self,
        question: str,
        generator: SQLGenerator | None = None,
        provider: Provider | None = None,
        context: list[Turn] | None = None,
        on_event: EventHandler | None = None,
    ) -> Answer:
        return answer(
            question,
            generator or self.generator_for(question, provider, context),
            self.engine,
            self.schema.dialect,
            max_retries=self.settings.max_retries,
            row_limit=self.settings.row_limit,
            on_event=on_event,
        )

    def run(self, sql: str) -> Answer:
        return run_sql(sql, self.engine, self.schema.dialect, self.settings.row_limit)
