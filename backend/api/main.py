"""HTTP API consumed by the Next.js frontend."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import queue
import threading
from collections.abc import AsyncIterator, Iterator
from functools import lru_cache
from typing import Annotated, Literal

import anthropic
import httpx
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from askdb.config import get_settings
from askdb.execute import Answer, AnswerError, Attempt, export_rows, fetch_rows
from askdb.generate import CannotAnswerError, GenerationError, Turn
from askdb.importers import UploadError
from askdb.pipeline import AskDB
from askdb.present import describe_result, pick_chart, to_json_value
from askdb.providers import (
    HOSTED,
    PROVIDERS,
    ModelNotAllowed,
    Provider,
    fetch_hosted_models,
    hosted_config,
    list_models,
    resolve_model,
)
from askdb.sources import SAMPLE_ID, SourceRegistry, valid_owner
from askdb.store import Store
from askdb.validate import InvalidSQLError, UnsafeQueryError, validate_sql

log = logging.getLogger("askdb.api")

app = FastAPI(title="AskDB API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@lru_cache
def get_registry() -> SourceRegistry:
    return SourceRegistry()


Registry = Annotated[SourceRegistry, Depends(get_registry)]


@lru_cache
def get_store() -> Store:
    s = get_settings()
    return Store(s.store_path, s.max_saved_answers)


AppStore = Annotated[Store, Depends(get_store)]

# The user's own key for the chosen provider, kept in their browser and sent with
# each request. It's used for that request only: never stored or logged.
UserKey = Annotated[str | None, Header(alias="X-AskDB-Api-Key", max_length=512)]


# A random id the browser keeps in localStorage. Uploads belong to the id that
# made them, so one visitor can't see or delete another's databases.
Owner = Annotated[str | None, Header(alias="X-AskDB-Owner", max_length=128)]


def _key(value: str | None) -> str | None:
    return value.strip() or None if value else None


def resolve(registry: SourceRegistry, database: str | None, owner: str | None) -> AskDB:
    """The pipeline for a database id (None or "sample" = the configured database)."""
    try:
        return registry.get(database, owner)
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
    # A model the provider offers (see /api/models). None uses the provider's default.
    model: str | None = Field(default=None, max_length=200)
    # Earlier turns of the conversation, oldest first, for follow-up questions.
    context: list[TurnIn] = Field(default_factory=list, max_length=5)
    # Which database to ask (None = the configured sample).
    database: str | None = None


class RunRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=5000)
    database: str | None = None


class RowsRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=5000)
    database: str | None = None
    offset: int = Field(ge=0)
    limit: int = Field(default=500, ge=1)


class ExportRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=5000)
    database: str | None = None


class ConnectRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    name: str | None = Field(default=None, max_length=80)


class ShareRequest(BaseModel):
    shared: bool = True


class FeedbackRequest(BaseModel):
    answer_id: str | None = Field(default=None, max_length=32)
    database: str | None = None
    question: str = Field(min_length=1, max_length=1000)
    sql: str = Field(min_length=1, max_length=5000)
    rating: Literal[1, -1]
    # The SQL the user edited the answer into, when they fixed it.
    corrected_sql: str | None = Field(default=None, max_length=5000)
    comment: str | None = Field(default=None, max_length=1000)
    provider: str | None = Field(default=None, max_length=40)
    model: str | None = Field(default=None, max_length=200)


class AttemptOut(BaseModel):
    sql: str
    error: str | None
    stage: str | None


class ChartOut(BaseModel):
    type: str
    x: str | None
    y: list[str] | None
    reason: str
    group: str | None = None
    label: str | None = None


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
    # A plain-language answer, when summaries are on. While streaming it arrives
    # in a separate `summary` event after the result.
    summary: str | None = None
    # The saved answer's id (for share links and feedback), when history is on.
    id: str | None = None


class ErrorDetail(BaseModel):
    message: str
    attempts: list[AttemptOut] = []


# ---------------------------------------------------------------- helpers


def _attempts(attempts: list[Attempt]) -> list[AttemptOut]:
    return [AttemptOut(sql=a.sql, error=a.error, stage=a.stage) for a in attempts]


def to_response(ans: Answer, provider: str, model: str) -> AskResponse:
    rows = [[to_json_value(v) for v in r] for r in ans.result.rows]
    chart = pick_chart(ans.result.columns, rows, ans.question)
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
        return 401, ErrorDetail(
            message="The Anthropic API rejected the key. Check it under API keys."
        )
    if isinstance(e, anthropic.RateLimitError):
        return 429, ErrorDetail(message="Rate limited by the model API; try again.")
    if isinstance(e, anthropic.APIError):
        return 502, ErrorDetail(message=f"Model API error: {e.message}")
    if isinstance(e, anthropic.AnthropicError):  # e.g. no credentials configured
        return 401, ErrorDetail(
            message="No Anthropic key. Add yours under API keys (the key button at the "
            "top of the page), or switch to the Free model."
        )
    log.exception("Unexpected error", exc_info=e)
    return 500, ErrorDetail(message="Unexpected server error. Check the backend logs.")


def _context(req: AskRequest) -> list[Turn]:
    return [Turn(question=t.question, sql=t.sql) for t in req.context]


def _database_id(database: str | None) -> str:
    return database or SAMPLE_ID


def _feedback_examples(store: Store, database: str | None, owner: str | None):
    """This browser's verified question/SQL pairs for this database."""
    if not valid_owner(owner) or get_settings().feedback_examples <= 0:
        return None
    return [(e.question, e.sql) for e in store.examples(_database_id(database), owner)]


def _save(store: Store, owner: str | None, database: str | None, res: AskResponse) -> None:
    """Save an answer to this browser's history (sets res.id)."""
    if not valid_owner(owner) or not get_settings().save_history:
        return
    try:
        res.id = store.save_answer(owner, _database_id(database), res.model_dump())
    except Exception:  # history is a convenience; never fail the answer over it
        log.exception("Could not save the answer")


def _require_owner(owner: str | None) -> str:
    if not valid_owner(owner):
        raise HTTPException(
            400,
            ErrorDetail(
                message="Your browser didn't send an id. Reload the page and try again."
            ).model_dump(),
        )
    return owner


def _model(db: AskDB, provider: Provider, model: str | None, api_key: str | None) -> str:
    """The model for this request; 400 if the user may not use the one they picked."""
    try:
        return resolve_model(db.settings, provider, model, api_key)
    except ModelNotAllowed as e:
        raise HTTPException(400, ErrorDetail(message=str(e)).model_dump()) from None


# ---------------------------------------------------------------- routes


@app.get("/", include_in_schema=False)
def root() -> dict:
    # Opening the API port in a browser shouldn't look like a broken app.
    return {
        "name": "AskDB API",
        "message": "This is the backend. Open the web app at http://localhost:3000.",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
def health(registry: Registry, owner: Owner = None, database: str | None = Query(None)) -> dict:
    db = resolve(registry, database, owner)
    return {
        "status": "ok",
        "dialect": db.schema.dialect,
        "tables": len(db.schema.tables),
        "default_provider": db.default_provider,
        "providers": {p: db.model_name(p) for p in PROVIDERS},
        "configured": db.configured,
    }


@app.get("/api/schema")
def schema(registry: Registry, owner: Owner = None, database: str | None = Query(None)) -> dict:
    db = resolve(registry, database, owner)
    return db.schema.to_dict() | {"suggestions": registry.suggestions(database, owner)}


@app.get("/api/databases")
def list_databases(registry: Registry, owner: Owner = None) -> dict:
    s = registry.settings
    return {
        "databases": [info.to_dict() for info in registry.list(owner)],
        "allow_uploads": s.allow_uploads,
        "allow_connections": s.allow_connections,
        "max_upload_mb": s.max_upload_mb,
        "save_history": s.save_history,
    }


@app.post("/api/databases")
async def upload_database(
    registry: Registry,
    files: Annotated[list[UploadFile], File(description="One SQLite file, or CSV files")],
    name: Annotated[str | None, Form(max_length=80)] = None,
    owner: Owner = None,
) -> dict:
    """Create a queryable database from an uploaded SQLite file or CSV files.
    Only the uploading browser (its X-AskDB-Owner id) can see it."""
    if not valid_owner(owner):
        raise HTTPException(
            400,
            ErrorDetail(
                message="Your browser didn't send an id, so the upload couldn't be saved "
                "as yours. Reload the page and try again."
            ).model_dump(),
        )
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
        info = registry.add(loaded, name, owner)
    except UploadError as e:
        raise HTTPException(400, ErrorDetail(message=str(e)).model_dump()) from e
    return info.to_dict()


@app.post("/api/databases/connect")
def connect_database(req: ConnectRequest, registry: Registry, owner: Owner = None) -> dict:
    """Add a live PostgreSQL or MySQL database by connection string. Only this
    browser can see it; the connection string is never sent back."""
    owner = _require_owner(owner)
    try:
        info = registry.connect(req.url, req.name, owner)
    except UploadError as e:
        raise HTTPException(400, ErrorDetail(message=str(e)).model_dump()) from e
    return info.to_dict()


@app.delete("/api/databases/{database}")
def delete_database(
    database: str, registry: Registry, store: AppStore, owner: Owner = None
) -> dict:
    try:
        registry.delete(database, owner)
    except KeyError:
        raise HTTPException(404, ErrorDetail(message="No such database.").model_dump()) from None
    except UploadError as e:
        raise HTTPException(400, ErrorDetail(message=str(e)).model_dump()) from e
    store.delete_database(database)
    return {"deleted": database}


@app.post("/api/ask", response_model=AskResponse, responses={422: {"model": ErrorDetail}})
def ask(
    req: AskRequest,
    registry: Registry,
    store: AppStore,
    api_key: UserKey = None,
    owner: Owner = None,
) -> AskResponse:
    # Sync endpoint: FastAPI runs it in a worker thread, so the blocking SDK
    # and DB calls don't stall the event loop.
    db = resolve(registry, req.database, owner)
    provider = req.provider or db.default_provider
    model = _model(db, provider, req.model, _key(api_key))
    try:
        ans = db.ask(
            req.question.strip(),
            provider=provider,
            context=_context(req),
            api_key=_key(api_key),
            model=model,
            extra_examples=_feedback_examples(store, req.database, owner),
        )
    except Exception as e:
        status, detail = error_detail(e)
        raise HTTPException(status, detail.model_dump()) from e
    res = to_response(ans, provider, model)
    res.summary = db.summarize(ans, provider, _key(api_key), model)
    _save(store, owner, req.database, res)
    return res


# While the model thinks, send an SSE comment this often so proxies and browsers
# don't close a connection that looks idle.
KEEPALIVE_S = 15.0


class ClientGone(Exception):
    """The client disconnected, so the answer is no longer wanted."""


@app.post("/api/ask/stream")
def ask_stream(
    req: AskRequest,
    request: Request,
    registry: Registry,
    store: AppStore,
    api_key: UserKey = None,
    owner: Owner = None,
) -> StreamingResponse:
    """Same as /api/ask, as Server-Sent Events: progress events while the pipeline
    runs, then one `result` or `error` event. After a result comes a `summary`
    event (the plain-language answer), so the table shows without waiting for it.

    If the client disconnects, the pipeline stops at its next step, so a closed tab
    doesn't keep spending model calls on repairs nobody will see.
    """
    db = resolve(registry, req.database, owner)
    provider = req.provider or db.default_provider
    model = _model(db, provider, req.model, _key(api_key))
    events: queue.Queue[dict | None] = queue.Queue()
    gone = threading.Event()

    def on_event(event: dict) -> None:
        # Called before each pipeline step, including every model call.
        if gone.is_set():
            raise ClientGone
        events.put(event)

    def work() -> None:
        try:
            ans = db.ask(
                req.question.strip(),
                provider=provider,
                context=_context(req),
                on_event=on_event,
                api_key=_key(api_key),
                model=model,
                extra_examples=_feedback_examples(store, req.database, owner),
            )
            result = to_response(ans, provider, model)
            _save(store, owner, req.database, result)
            events.put({"type": "result", "data": result.model_dump()})
            if gone.is_set():
                return
            events.put({"type": "stage", "stage": "summarize"})
            summary = db.summarize(ans, provider, _key(api_key), model)
            if summary:
                if result.id:
                    store.update_answer(owner, result.id, {"summary": summary})
                events.put({"type": "summary", "text": summary})
        except ClientGone:
            log.info("Client disconnected; stopped answering %r", req.question[:80])
        except Exception as e:  # reported to the client as an event
            status, detail = error_detail(e)
            events.put({"type": "error", "status": status, "detail": detail.model_dump()})
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    async def stream() -> AsyncIterator[str]:
        try:
            while True:
                try:
                    event = await asyncio.to_thread(events.get, timeout=KEEPALIVE_S)
                except queue.Empty:
                    if await request.is_disconnected():
                        return
                    yield ": keepalive\n\n"
                    continue
                if event is None:
                    return
                yield f"data: {json.dumps(event, default=str)}\n\n"
        finally:
            # Runs when the stream ends for any reason, including the server
            # cancelling it because the client went away.
            gone.set()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/run", response_model=AskResponse, responses={422: {"model": ErrorDetail}})
def run(req: RunRequest, registry: Registry, owner: Owner = None) -> AskResponse:
    """Run SQL the user edited. Same read-only validation and connection."""
    db = resolve(registry, req.database, owner)
    try:
        ans = db.run(req.sql)
    except Exception as e:
        status, detail = error_detail(e)
        raise HTTPException(status, detail.model_dump()) from e
    res = to_response(ans, "manual", "Edited by you")
    if db.settings.summaries != "off":
        res.summary = describe_result(ans.result.columns, ans.result.rows, ans.result.truncated)
    return res


@app.post("/api/rows")
def more_rows(req: RowsRequest, registry: Registry, owner: Owner = None) -> dict:
    """The next page of an answer's rows: the same SQL, re-validated, from `offset`."""
    db = resolve(registry, req.database, owner)
    limit = min(req.limit, db.settings.max_page_rows)
    try:
        result = fetch_rows(req.sql, db.engine, db.schema.dialect, limit, req.offset)
    except Exception as e:
        status, detail = error_detail(e)
        raise HTTPException(status, detail.model_dump()) from e
    return {
        "columns": result.columns,
        "rows": [[to_json_value(v) for v in r] for r in result.rows],
        "truncated": result.truncated,
    }


@app.post("/api/export")
def export_csv(req: ExportRequest, registry: Registry, owner: Owner = None) -> StreamingResponse:
    """Every row of an answer as CSV (up to ASKDB_EXPORT_ROW_LIMIT), streamed."""
    db = resolve(registry, req.database, owner)
    try:
        columns, rows = export_rows(
            req.sql, db.engine, db.schema.dialect, db.settings.export_row_limit
        )
    except Exception as e:
        status, detail = error_detail(e)
        raise HTTPException(status, detail.model_dump()) from e

    def lines() -> Iterator[str]:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(columns)
        for i, row in enumerate(rows, 1):
            writer.writerow(["" if v is None else to_json_value(v) for v in row])
            if i % 500 == 0:
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate()
        yield buf.getvalue()

    return StreamingResponse(
        lines(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="askdb-result.csv"'},
    )


# ---------------------------------------------------------------- history


@app.get("/api/history")
def history(
    store: AppStore,
    owner: Owner = None,
    database: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """This browser's saved answers, newest first (for one database, or all)."""
    if not valid_owner(owner):
        return {"answers": []}
    return {"answers": [a.__dict__ for a in store.list_answers(owner, database, limit)]}


@app.get("/api/history/{answer_id}")
def saved_answer(answer_id: str, store: AppStore, owner: Owner = None) -> dict:
    """A saved answer: this browser's own, or anyone's that has been shared."""
    found = store.get_answer(owner, answer_id)
    if found is None:
        raise HTTPException(
            404, ErrorDetail(message="That answer doesn't exist or isn't shared.").model_dump()
        )
    return found


@app.post("/api/history/{answer_id}/share")
def share_answer(answer_id: str, req: ShareRequest, store: AppStore, owner: Owner = None) -> dict:
    """Let anyone with the link see this saved answer (its question, SQL, and the
    rows it returned), or stop sharing it."""
    if not store.share_answer(_require_owner(owner), answer_id, req.shared):
        raise HTTPException(404, ErrorDetail(message="No such answer.").model_dump())
    return {"id": answer_id, "shared": req.shared}


@app.delete("/api/history/{answer_id}")
def delete_answer(answer_id: str, store: AppStore, owner: Owner = None) -> dict:
    deleted = store.delete_answers(_require_owner(owner), answer_id=answer_id)
    if not deleted:
        raise HTTPException(404, ErrorDetail(message="No such answer.").model_dump())
    return {"deleted": deleted}


@app.delete("/api/history")
def clear_history(store: AppStore, owner: Owner = None, database: str | None = Query(None)) -> dict:
    """Delete this browser's saved answers for a database (or all of them)."""
    return {"deleted": store.delete_answers(_require_owner(owner), database=database)}


# ---------------------------------------------------------------- feedback


@app.post("/api/feedback")
def feedback(
    req: FeedbackRequest, registry: Registry, store: AppStore, owner: Owner = None
) -> dict:
    """Record 👍/👎 on an answer, with the corrected SQL if the user fixed it.
    Verified pairs are reused as examples in this browser's prompts for this
    database, and can be exported as eval cases (eval/export_feedback.py)."""
    owner = _require_owner(owner)
    db = resolve(registry, req.database, owner)
    corrected = (req.corrected_sql or "").strip() or None
    if corrected:
        try:
            corrected = validate_sql(corrected, db.schema.dialect)
        except (UnsafeQueryError, InvalidSQLError) as e:
            raise HTTPException(
                400, ErrorDetail(message=f"The corrected SQL isn't valid: {e}").model_dump()
            ) from e
    feedback_id = store.add_feedback(
        owner,
        _database_id(req.database),
        req.question.strip(),
        req.sql.strip(),
        req.rating,
        corrected_sql=corrected,
        comment=(req.comment or "").strip() or None,
        answer_id=req.answer_id,
        provider=req.provider,
        model=req.model,
    )
    return {"id": feedback_id}


@app.get("/api/models")
def models(
    registry: Registry,
    provider: Annotated[Provider, Query()],
    api_key: UserKey = None,
) -> dict:
    """The models to offer for a provider. With the user's own key, hosted providers
    list everything that key can use; with the server's key, only what the operator
    allowed (ASKDB_*_MODELS)."""
    result = list_models(registry.settings, provider, _key(api_key))
    return {"provider": provider} | result.__dict__


class KeyCheckRequest(BaseModel):
    provider: Literal["claude", "free", "groq", "openrouter", "openai"]


@app.post("/api/keys/check")
def check_key(req: KeyCheckRequest, api_key: UserKey = None) -> dict:
    """Try a key with a cheap call that lists models (no tokens are used)."""
    key = _key(api_key)
    if not key:
        return {"ok": False, "message": "Paste a key first."}
    settings = get_settings()
    try:
        if req.provider in HOSTED:
            with httpx.Client(timeout=15) as client:
                fetch_hosted_models(hosted_config(settings, req.provider).base_url, key, client)
        else:
            with anthropic.Anthropic(api_key=key, max_retries=0, timeout=15) as client:
                client.models.list(limit=1)
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        bad = code in (400, 401, 403)
        return {"ok": False, "message": "That key was rejected." if bad else f"HTTP {code}."}
    except anthropic.AuthenticationError:
        return {"ok": False, "message": "That key was rejected."}
    except (httpx.HTTPError, anthropic.APIError) as e:
        return {"ok": False, "message": f"Couldn't reach the provider: {type(e).__name__}."}
    return {"ok": True, "message": "Key works."}
