"""Stage 5: validate, run, and self-correct on failure."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Engine

from askdb.db import QueryError, QueryResult, run_query
from askdb.generate import Repair, SQLGenerator
from askdb.validate import InvalidSQLError, UnsafeQueryError, validate_sql


@dataclass
class Attempt:
    sql: str
    error: str | None = None
    stage: str | None = None  # "validate" or "execute" when the attempt failed


@dataclass
class Answer:
    question: str
    sql: str
    explanation: str
    result: QueryResult
    attempts: list[Attempt] = field(default_factory=list)


class AnswerError(Exception):
    """Every attempt failed. Carries the attempts so the UI can show what happened."""

    def __init__(self, message: str, attempts: list[Attempt]):
        super().__init__(message)
        self.attempts = attempts


EventHandler = Callable[[dict[str, Any]], None]


def _check_and_run(
    attempt: Attempt, engine: Engine, dialect: str, row_limit: int, emit: EventHandler
) -> tuple[str, QueryResult] | None:
    """Validate then execute one attempt. Records the failure on the attempt and returns
    None if either step fails. Unsafe SQL never reaches the database."""
    emit({"type": "stage", "stage": "validate"})
    try:
        sql = validate_sql(attempt.sql, dialect)
    except UnsafeQueryError as e:
        attempt.error, attempt.stage = f"Blocked: {e}", "validate"
        return None
    except InvalidSQLError as e:
        attempt.error, attempt.stage = f"Syntax error: {e}", "validate"
        return None
    emit({"type": "stage", "stage": "execute"})
    try:
        return sql, run_query(engine, sql, row_limit)
    except QueryError as e:
        attempt.error, attempt.stage = str(e), "execute"
        return None


def answer(
    question: str,
    generator: SQLGenerator,
    engine: Engine,
    dialect: str,
    max_retries: int = 2,
    row_limit: int = 100,
    on_event: EventHandler | None = None,
) -> Answer:
    """Generate SQL, then validate and run it, feeding any error back for repair.

    Both validation failures (bad syntax, a write statement) and database errors
    are sent back to the model, up to ``max_retries`` repairs. Unsafe SQL is
    never executed. ``on_event`` receives progress events for live UIs.
    """
    emit = on_event or (lambda _event: None)
    attempts: list[Attempt] = []
    repairs: list[Repair] = []

    for attempt_no in range(max_retries + 1):
        emit({"type": "stage", "stage": "generate", "attempt": attempt_no + 1})
        gen = generator.generate(question, repairs or None)
        attempt = Attempt(sql=gen.sql)
        attempts.append(attempt)
        emit({"type": "generated", "attempt": attempt_no + 1, "sql": gen.sql})

        outcome = _check_and_run(attempt, engine, dialect, row_limit, emit)
        if outcome:
            sql, result = outcome
            return Answer(question, sql, gen.explanation, result, attempts)

        emit(
            {
                "type": "attempt_failed",
                "attempt": attempt_no + 1,
                "stage": attempt.stage,
                "error": attempt.error,
                "sql": attempt.sql,
                "will_retry": attempt_no < max_retries,
            }
        )
        if attempt_no < max_retries:
            repairs.append(Repair(sql=gen.sql, error=attempt.error))

    raise AnswerError(f"Could not answer after {len(attempts)} attempts.", attempts)


def run_sql(sql: str, engine: Engine, dialect: str, row_limit: int = 100) -> Answer:
    """Run SQL a person wrote or edited, behind the same read-only gate."""
    attempt = Attempt(sql=sql.strip())
    outcome = _check_and_run(attempt, engine, dialect, row_limit, lambda _event: None)
    if not outcome:
        raise AnswerError(attempt.error or "Query failed.", [attempt])
    final_sql, result = outcome
    return Answer("Edited SQL", final_sql, "", result, [attempt])
