"""HTTP API consumed by the Next.js frontend."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

import anthropic
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from askdb.config import get_settings
from askdb.execute import AnswerError, Attempt
from askdb.generate import CannotAnswerError, GenerationError
from askdb.pipeline import AskDB, Provider
from askdb.present import ChartSpec, pick_chart, to_json_value

app = FastAPI(title="AskDB API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@lru_cache
def get_askdb() -> AskDB:
    return AskDB.from_settings()


DB = Annotated[AskDB, Depends(get_askdb)]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    # None uses the server default (ASKDB_PROVIDER).
    provider: Provider | None = None


class AttemptOut(BaseModel):
    sql: str
    error: str | None
    stage: str | None


class ChartOut(BaseModel):
    type: str
    x: str | None
    y: list[str] | None
    reason: str


class AskResponse(BaseModel):
    question: str
    provider: Provider
    model: str
    sql: str
    explanation: str
    columns: list[str]
    rows: list[list]
    truncated: bool
    chart: ChartOut
    attempts: list[AttemptOut]


class ErrorDetail(BaseModel):
    message: str
    attempts: list[AttemptOut] = []


def _attempts(attempts: list[Attempt]) -> list[AttemptOut]:
    return [AttemptOut(sql=a.sql, error=a.error, stage=a.stage) for a in attempts]


@app.get("/api/health")
def health(db: DB) -> dict:
    return {
        "status": "ok",
        "dialect": db.schema.dialect,
        "tables": len(db.schema.tables),
        "default_provider": db.settings.provider,
        "providers": {"claude": db.model_name("claude"), "local": db.model_name("local")},
    }


@app.get("/api/schema")
def schema(db: DB) -> dict:
    return db.schema.to_dict()


@app.post("/api/ask", response_model=AskResponse, responses={422: {"model": ErrorDetail}})
def ask(req: AskRequest, db: DB) -> AskResponse:
    # Sync endpoint: FastAPI runs it in a worker thread, so the blocking SDK
    # and DB calls don't stall the event loop.
    provider = req.provider or db.settings.provider
    try:
        ans = db.ask(req.question.strip(), provider=provider)
    except AnswerError as e:
        raise HTTPException(
            422, ErrorDetail(message=str(e), attempts=_attempts(e.attempts)).model_dump()
        ) from e
    except CannotAnswerError as e:
        raise HTTPException(422, ErrorDetail(message=str(e)).model_dump()) from e
    except GenerationError as e:
        raise HTTPException(502, ErrorDetail(message=str(e)).model_dump()) from e
    except anthropic.AuthenticationError as e:
        raise HTTPException(
            500, ErrorDetail(message="Anthropic API key is missing or invalid.").model_dump()
        ) from e
    except anthropic.RateLimitError as e:
        raise HTTPException(
            429, ErrorDetail(message="Rate limited by the model API; try again.").model_dump()
        ) from e
    except anthropic.APIError as e:
        raise HTTPException(
            502, ErrorDetail(message=f"Model API error: {e.message}").model_dump()
        ) from e
    except anthropic.AnthropicError as e:  # e.g. no credentials configured
        raise HTTPException(500, ErrorDetail(message=str(e)).model_dump()) from e

    rows = [[to_json_value(v) for v in r] for r in ans.result.rows]
    chart: ChartSpec = pick_chart(ans.result.columns, rows)
    return AskResponse(
        question=ans.question,
        provider=provider,
        model=db.model_name(provider),
        sql=ans.sql,
        explanation=ans.explanation,
        columns=ans.result.columns,
        rows=rows,
        truncated=ans.result.truncated,
        chart=ChartOut(**chart.__dict__),
        attempts=_attempts(ans.attempts),
    )
