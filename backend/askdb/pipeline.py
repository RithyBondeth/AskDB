"""Wire the stages together behind one object the CLI, API, and eval share."""

from __future__ import annotations

from dataclasses import dataclass, field

import anthropic
from sqlalchemy import Engine

from askdb.config import Settings, get_settings
from askdb.db import make_engine
from askdb.execute import Answer, answer
from askdb.generate import ClaudeGenerator, SQLGenerator, build_system_prompt
from askdb.schema import Schema, introspect, link_tables


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

    def generator_for(self, question: str) -> SQLGenerator:
        tables = link_tables(self.schema, question)
        system = build_system_prompt(
            dialect=self.schema.dialect,
            schema_ddl=self.schema.ddl(tables),
            row_limit=self.settings.row_limit,
            reference_date=self.settings.reference_date,
        )
        return ClaudeGenerator(
            system, model=self.settings.model, effort=self.settings.effort, client=self.client
        )

    def ask(self, question: str, generator: SQLGenerator | None = None) -> Answer:
        return answer(
            question,
            generator or self.generator_for(question),
            self.engine,
            self.schema.dialect,
            max_retries=self.settings.max_retries,
            row_limit=self.settings.row_limit,
        )
