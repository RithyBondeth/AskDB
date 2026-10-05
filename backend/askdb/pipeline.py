"""Wire the stages together behind one object the CLI, API, and eval share."""

from __future__ import annotations

import datetime as dt
import logging
import os
from dataclasses import dataclass, field

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
from askdb.linking import OpenAIEmbedder, SchemaIndex, tokens
from askdb.local import LocalGenerator
from askdb.present import describe_result
from askdb.prompts import FEW_SHOT_EXAMPLES
from askdb.providers import HOSTED, PROVIDERS, Provider, default_model, hosted_config
from askdb.schema import Schema, introspect

log = logging.getLogger("askdb.pipeline")

MISSING_ANTHROPIC_KEY = (
    "No Anthropic key. Add yours under API keys (the key button at the top of the page), "
    "set ANTHROPIC_API_KEY on the server, or switch to the Free model."
)

__all__ = ["AskDB", "Provider", "PROVIDERS"]


def make_embedder(settings: Settings) -> OpenAIEmbedder | None:
    """The embedding model for schema linking, if one is configured."""
    if not settings.embedding_model:
        return None
    key = settings.embedding_api_key or settings.free_api_key
    return OpenAIEmbedder(
        settings.embedding_base_url or settings.free_base_url,
        settings.embedding_model,
        key.get_secret_value() if key else None,
    )


def similar_examples(
    question: str, examples: list[tuple[str, str]], k: int
) -> list[tuple[str, str]]:
    """The `k` examples whose questions share the most words with `question`."""
    if k <= 0 or not examples:
        return []
    words = set(tokens(question))
    scored = [(len(words & set(tokens(q))), i) for i, (q, _) in enumerate(examples)]
    best = sorted((s for s in scored if s[0] > 0), key=lambda s: (-s[0], s[1]))[:k]
    return [examples[i] for _, i in best]


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
    _index: SchemaIndex | None = field(default=None, repr=False)

    @property
    def index(self) -> SchemaIndex:
        """Retrieval over this database's tables, built on first use."""
        if self._index is None:
            self._index = SchemaIndex(self.schema, make_embedder(self.settings))
        return self._index

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
        return cls.for_database(f"sqlite:///{path}", settings, client)

    @classmethod
    def for_database(
        cls, url: str, settings: Settings | None = None, client: anthropic.Anthropic | None = None
    ) -> AskDB:
        """An uploaded file or a database someone connected: no schema-specific
        examples, real dates."""
        settings = settings or get_settings()
        engine = make_engine(url, settings.statement_timeout_s)
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
        out = {p: hosted_config(self.settings, p).api_key is not None for p in HOSTED}
        return out | {"claude": self.has_anthropic_credentials, "local": True}

    @property
    def default_provider(self) -> Provider:
        p = self.settings.provider
        if p != "auto":
            return p
        return "claude" if self.has_anthropic_credentials else "free"

    def model_name(self, provider: Provider | None = None) -> str:
        """The default model for a provider."""
        return default_model(self.settings, provider or self.default_provider)

    def generator_for(
        self,
        question: str,
        provider: Provider | None = None,
        context: list[Turn] | None = None,
        api_key: str | None = None,
        model: str | None = None,
        extra_examples: list[tuple[str, str]] | None = None,
    ) -> SQLGenerator:
        """The generator for a provider. `api_key` is the user's own key for that
        provider (from the browser); it takes precedence over the server's key.
        `model` must already be checked (askdb.providers.resolve_model); None uses
        the provider's default. `extra_examples` are verified question/SQL pairs
        (from feedback); the ones most like this question join the prompt."""
        provider = provider or self.default_provider
        model = model or self.model_name(provider)
        # Link on the whole conversation so follow-ups keep the tables they build on.
        linking_text = " ".join([*(t.question for t in context or []), question])
        tables = self.index.link(linking_text)
        known = {q.strip().lower() for q, _ in self.examples}
        extra = [e for e in extra_examples or [] if e[0].strip().lower() not in known]
        examples = self.examples + similar_examples(
            question, extra, self.settings.feedback_examples
        )
        if provider == "local":
            return LocalGenerator(
                dialect=self.schema.dialect,
                schema_ddl=self.schema.ddl(tables),
                model=model,
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
            examples=examples,
        )
        if provider != "claude":
            cfg = hosted_config(self.settings, provider)
            return HostedGenerator(
                system,
                model=model,
                base_url=cfg.base_url,
                api_key=api_key or cfg.api_key,
                context=context,
                timeout_s=self.settings.free_timeout_s,
                provider=provider,
                label=cfg.label,
            )
        if not api_key and not self.has_anthropic_credentials:
            raise GenerationError(MISSING_ANTHROPIC_KEY)
        return ClaudeGenerator(
            system,
            model=model,
            effort=self.settings.effort,
            # The user's own key gets a client for this request only.
            client=None if api_key else self.client,
            api_key=api_key,
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
        model: str | None = None,
        extra_examples: list[tuple[str, str]] | None = None,
    ) -> Answer:
        own = generator is None
        gen = generator or self.generator_for(
            question, provider, context, api_key, model, extra_examples
        )
        try:
            return answer(
                question,
                gen,
                self.engine,
                self.schema.dialect,
                max_retries=self.settings.max_retries,
                row_limit=self.settings.row_limit,
                on_event=on_event,
            )
        finally:
            # Generators are built per question; release their HTTP connections.
            if own and (close := getattr(gen, "close", None)):
                close()

    def summarize(
        self,
        ans: Answer,
        provider: Provider | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> str | None:
        """A plain-language sentence answering the question from the result.

        Asks the model that wrote the SQL when ASKDB_SUMMARIES=model (except the
        open model, which is tuned for SQL only); otherwise, or if that call fails,
        a template sentence. None when summaries are off.
        """
        mode = self.settings.summaries
        if mode == "off":
            return None
        rows, columns = ans.result.rows, ans.result.columns
        provider = provider or self.default_provider
        if mode == "model" and provider != "local" and rows:
            gen = None
            try:
                gen = self.generator_for(ans.question, provider, None, api_key, model)
                text = gen.summarize(ans.question, columns, rows, ans.result.truncated)
                if text:
                    return text
            except Exception as e:  # a summary is a nicety: never fail the answer
                log.info("Model summary failed, using a template: %s", e)
            finally:
                if gen is not None and (close := getattr(gen, "close", None)):
                    close()
        return describe_result(columns, rows, ans.result.truncated)

    def run(self, sql: str) -> Answer:
        return run_sql(sql, self.engine, self.schema.dialect, self.settings.row_limit)
