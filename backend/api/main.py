"""HTTP API consumed by the Next.js frontend."""

from __future__ import annotations

import json
import logging
import queue
import threading
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated, Literal

import anthropic
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from askdb.config import get_settings
from askdb.execute import Answer, AnswerError, Attempt
from askdb.generate import CannotAnswerError, GenerationError, Turn
from askdb.importers import UploadError
from askdb.pipeline import AskDB, Provider
from askdb.present import pick_chart, to_json_value
from askdb.sources import SourceRegistry

log = logging.getLogger("askdb.api")

app = FastAPI(title="AskDB API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@lru_cache
def get_registry() -> SourceRegistry:
    return SourceRegistry()


Registry = Annotated[SourceRegistry, Depends(get_registry)]


def resolve(registry: SourceRegistry, database: str | None) -> AskDB:
    """The pipeline for a database id (None or "sample" = the configured database)."""
    try:
        return registry.get(database)
    except KeyError:
        raise HTTPException(
            404, ErrorDetail(message="That database no longer exists.").model_dump()
        ) from None


# ---------------------------------------------------------------- models


class TurnIn(BaseModel):
    question: str = Field(max_length=1000)
    sql: str = Field(max_length=5000)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    # None uses the server default (ASKDB_PROVIDER).
    provider: Provider | None = None
    # Earlier turns of the conversation, oldest first, for follow-up questions.
    context: list[TurnIn] = Field(default_factory=list, max_length=5)
    # Which database to ask (None = the configured sample).
    database: str | None = None


class RunRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=5000)
    database: str | None = None


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
    provider: Provider | Literal["manual"]
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


# ---------------------------------------------------------------- helpers


def _attempts(attempts: list[Attempt]) -> list[AttemptOut]:
    return [AttemptOut(sql=a.sql, error=a.error, stage=a.stage) for a in attempts]


def to_response(ans: Answer, provider: str, model: str) -> AskResponse:
    rows = [[to_json_value(v) for v in r] for r in ans.result.rows]
    chart = pick_chart(ans.result.columns, rows)
    return AskResponse(
        question=ans.question,
        provider=provider,
        model=model,
        sql=ans.sql,
        explanation=ans.explanation,
        columns=ans.result.columns,
        rows=rows,
        truncated=ans.result.truncated,
        chart=ChartOut(**chart.__dict__),
        attempts=_attempts(ans.attempts),
    )


def error_detail(e: Exception) -> tuple[int, ErrorDetail]:
    """Map pipeline and model errors to an HTTP status and a message for the UI."""
    if isinstance(e, AnswerError):
        return 422, ErrorDetail(message=str(e), attempts=_attempts(e.attempts))
    if isinstance(e, CannotAnswerError):
        return 422, ErrorDetail(message=str(e))
    if isinstance(e, GenerationError):
        return 502, ErrorDetail(message=str(e))
    if isinstance(e, anthropic.AuthenticationError):
        return 500, ErrorDetail(message="Anthropic API key is missing or invalid.")
    if isinstance(e, anthropic.RateLimitError):
        return 429, ErrorDetail(message="Rate limited by the model API; try again.")
    if isinstance(e, anthropic.APIError):
        return 502, ErrorDetail(message=f"Model API error: {e.message}")
    if isinstance(e, anthropic.AnthropicError):  # e.g. no credentials configured
        return 500, ErrorDetail(message=str(e))
    log.exception("Unexpected error", exc_info=e)
    return 500, ErrorDetail(message="Unexpected server error. Check the backend logs.")


def _context(req: AskRequest) -> list[Turn]:
    return [Turn(question=t.question, sql=t.sql) for t in req.context]


# ---------------------------------------------------------------- routes


@app.get("/api/health")
def health(registry: Registry, database: str | None = Query(None)) -> dict:
    db = resolve(registry, database)
    return {
        "status": "ok",
        "dialect": db.schema.dialect,
        "tables": len(db.schema.tables),
        "default_provider": db.default_provider,
        "providers": {p: db.model_name(p) for p in ("claude", "free", "local")},
        "configured": db.configured,
    }


@app.get("/api/schema")
def schema(registry: Registry, database: str | None = Query(None)) -> dict:
    db = resolve(registry, database)
    return db.schema.to_dict() | {"suggestions": registry.suggestions(database)}


@app.get("/api/databases")
def list_databases(registry: Registry) -> dict:
    s = registry.settings
    return {
        "databases": [info.to_dict() for info in registry.list()],
        "allow_uploads": s.allow_uploads,
        "max_upload_mb": s.max_upload_mb,
    }


@app.post("/api/databases")
async def upload_database(
    registry: Registry,
    files: Annotated[list[UploadFile], File(description="One SQLite file, or CSV files")],
    name: Annotated[str | None, Form(max_length=80)] = None,
) -> dict:
    """Create a queryable database from an uploaded SQLite file or CSV files."""
    limit = registry.settings.max_upload_mb * 1024 * 1024
    loaded: list[tuple[str, bytes]] = []
    total = 0
    for f in files:
        data = await f.read(limit - total + 1)  # never read more than the limit allows
        total += len(data)
        if total > limit:
            raise HTTPException(
                413,
                ErrorDetail(
                    message=f"Files are larger than {registry.settings.max_upload_mb} MB."
                ).model_dump(),
            )
        loaded.append((f.filename or "upload", data))
    try:
        info = registry.add(loaded, name)
    except UploadError as e:
        raise HTTPException(400, ErrorDetail(message=str(e)).model_dump()) from e
    return info.to_dict()


@app.delete("/api/databases/{database}")
def delete_database(database: str, registry: Registry) -> dict:
    try:
        registry.delete(database)
    except KeyError:
        raise HTTPException(404, ErrorDetail(message="No such database.").model_dump()) from None
    except UploadError as e:
        raise HTTPException(400, ErrorDetail(message=str(e)).model_dump()) from e
    return {"deleted": database}


@app.post("/api/ask", response_model=AskResponse, responses={422: {"model": ErrorDetail}})
def ask(req: AskRequest, registry: Registry) -> AskResponse:
    # Sync endpoint: FastAPI runs it in a worker thread, so the blocking SDK
    # and DB calls don't stall the event loop.
    db = resolve(registry, req.database)
    provider = req.provider or db.default_provider
    try:
        ans = db.ask(req.question.strip(), provider=provider, context=_context(req))
    except Exception as e:
        status, detail = error_detail(e)
        raise HTTPException(status, detail.model_dump()) from e
    return to_response(ans, provider, db.model_name(provider))


@app.post("/api/ask/stream")
def ask_stream(req: AskRequest, registry: Registry) -> StreamingResponse:
    """Same as /api/ask, as Server-Sent Events: progress events while the pipeline
    runs, then one `result` or `error` event."""
    db = resolve(registry, req.database)
    provider = req.provider or db.default_provider
    events: queue.Queue[dict | None] = queue.Queue()

    def work() -> None:
        try:
            ans = db.ask(
                req.question.strip(),
                provider=provider,
                context=_context(req),
                on_event=events.put,
            )
            result = to_response(ans, provider, db.model_name(provider))
            events.put({"type": "result", "data": result.model_dump()})
        except Exception as e:  # reported to the client as an event
            status, detail = error_detail(e)
            events.put({"type": "error", "status": status, "detail": detail.model_dump()})
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream() -> Iterator[str]:
        while (event := events.get()) is not None:
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/run", response_model=AskResponse, responses={422: {"model": ErrorDetail}})
def run(req: RunRequest, registry: Registry) -> AskResponse:
    """Run SQL the user edited. Same read-only validation and connection."""
    db = resolve(registry, req.database)
    try:
        ans = db.run(req.sql)
    except Exception as e:
        status, detail = error_detail(e)
        raise HTTPException(status, detail.model_dump()) from e
    return to_response(ans, "manual", "Edited by you")
