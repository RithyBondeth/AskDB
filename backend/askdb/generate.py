"""Stage 3: build the prompt and ask the LLM for SQL."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

import anthropic

from askdb.prompts import DATE_RULE, REPAIR_PROMPT, SYSTEM_PROMPT, render_examples


class GenerationError(Exception):
    """The model did not return usable SQL."""


class CannotAnswerError(GenerationError):
    """The model judged the question unanswerable from the schema."""


@dataclass
class Generation:
    sql: str
    explanation: str


@dataclass
class Repair:
    sql: str
    error: str


class SQLGenerator(Protocol):
    def generate(self, question: str, repairs: list[Repair] | None = None) -> Generation: ...


def build_system_prompt(
    dialect: str, schema_ddl: str, row_limit: int, reference_date: str | None
) -> str:
    return SYSTEM_PROMPT.format(
        dialect=dialect,
        schema_ddl=schema_ddl,
        row_limit=row_limit,
        date_rule=DATE_RULE.format(reference_date=reference_date) if reference_date else "",
        examples=render_examples(),
    )


def build_messages(question: str, repairs: list[Repair] | None = None) -> list[dict]:
    """The question, then one assistant/user pair per failed attempt (error feedback)."""
    messages: list[dict] = [{"role": "user", "content": f"Q: {question}"}]
    for r in repairs or []:
        messages.append({"role": "assistant", "content": f"```sql\n{r.sql}\n```"})
        messages.append({"role": "user", "content": REPAIR_PROMPT.format(sql=r.sql, error=r.error)})
    return messages


_SQL_BLOCK = re.compile(r"```(?:sql)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def parse_response(text: str) -> Generation:
    if "CANNOT_ANSWER" in text and "```" not in text:
        raise CannotAnswerError(text.replace("CANNOT_ANSWER", "").strip(" :.\n") or text)
    match = _SQL_BLOCK.search(text)
    if not match:
        raise GenerationError("Model response did not contain a SQL code block.")
    sql = match.group(1).strip()
    explanation = _SQL_BLOCK.sub("", text).strip()
    return Generation(sql=sql, explanation=explanation)


class ClaudeGenerator:
    """Generates SQL with Claude via the Anthropic SDK."""

    def __init__(
        self,
        system_prompt: str,
        model: str = "claude-opus-5-5",
        effort: str = "medium",
        client: anthropic.Anthropic | None = None,
    ):
        self.system_prompt = system_prompt
        self.model = model
        self.effort = effort
        self.client = client or anthropic.Anthropic()

    def generate(self, question: str, repairs: list[Repair] | None = None) -> Generation:
        try:
            response = self._request(question, repairs)
        except TypeError as e:  # raised by the SDK when no credentials are configured
            if "authentication" not in str(e).lower():
                raise
            raise GenerationError(
                "No Anthropic credentials found. Set ANTHROPIC_API_KEY (see .env.example)."
            ) from e
        if response.stop_reason == "refusal":
            raise GenerationError("The model declined to answer this question.")
        text = "".join(b.text for b in response.content if b.type == "text")
        return parse_response(text)

    def _request(self, question: str, repairs: list[Repair] | None):
        return self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            # The system prompt (schema + examples) is identical across questions,
            # so cache it.
            system=[
                {
                    "type": "text",
                    "text": self.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=build_messages(question, repairs),
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort},
            # If a safety classifier declines, let the API retry on its
            # recommended fallback model instead of failing the request.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
