"""Stage 5: validate, run, and self-correct on failure."""

from __future__ import annotations

from dataclasses import dataclass, field

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


def answer(
    question: str,
    generator: SQLGenerator,
    engine: Engine,
    dialect: str,
    max_retries: int = 2,
    row_limit: int = 100,
) -> Answer:
    """Generate SQL, then validate and run it, feeding any error back for repair.

    Both validation failures (bad syntax, a write statement) and database errors
    are sent back to the model, up to ``max_retries`` repairs. Unsafe SQL is
    never executed.
    """
    attempts: list[Attempt] = []
    repairs: list[Repair] = []

    for attempt_no in range(max_retries + 1):
        gen = generator.generate(question, repairs or None)
        attempt = Attempt(sql=gen.sql)
        attempts.append(attempt)

        try:
            sql = validate_sql(gen.sql, dialect)
        except UnsafeQueryError as e:
            attempt.error, attempt.stage = f"Blocked: {e}", "validate"
        except InvalidSQLError as e:
            attempt.error, attempt.stage = f"Syntax error: {e}", "validate"
        else:
            try:
                result = run_query(engine, sql, row_limit)
            except QueryError as e:
                attempt.error, attempt.stage = str(e), "execute"
            else:
                return Answer(question, sql, gen.explanation, result, attempts)

        if attempt_no < max_retries:
            repairs.append(Repair(sql=gen.sql, error=attempt.error))

    raise AnswerError(f"Could not answer after {len(attempts)} attempts.", attempts)
