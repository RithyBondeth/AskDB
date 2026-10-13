"""Token usage, estimated cost, request logs and the usage report."""

import json
import logging
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.main import app, get_registry
from askdb import usage
from askdb.config import Settings
from askdb.generate import ClaudeGenerator, Generation
from askdb.hosted import HostedGenerator
from askdb.local import LocalGenerator
from askdb.logs import _JsonFormatter, _TextFormatter
from askdb.sources import SourceRegistry
from askdb.usage import Price, Usage, metering, price_for

# ------------------------------------------------------------------ prices


def test_cost_counts_each_kind_of_token_at_its_rate():
    u = Usage("claude", "claude-opus-5-5", "sql", 1000, 500, 2000, 100)
    # 1000 in x $4 + 500 out x $20 + 2000 cache reads x $0.20 + 100 writes x $5 (1.25 x $4)
    assert price_for("claude", "claude-opus-5-5").cost(u) == pytest.approx(0.0149)


def test_which_models_have_prices():
    assert price_for("claude", "claude-sonnet-5-5") == Price(2.00, 10.00, cache_read=0.20)
    assert price_for("claude", "claude-unknown") is None
    assert price_for("local", "anything").cost(Usage("local", "m", "sql", 10**6, 10**6)) == 0
    assert price_for("free", "gemini-flash-latest") == Price(0, 0)
    assert price_for("groq", "openai/gpt-oss-120b") is None  # no guessing
    overrides = {"openai/gpt-oss-120b": Price(0.15, 0.60)}
    assert price_for("groq", "openai/gpt-oss-120b", overrides) == Price(0.15, 0.60)


def test_price_settings_are_checked_at_startup():
    s = Settings(model_prices={"gpt-5-mini": {"input": 0.25, "output": 2.0}})
    assert usage.parse_prices(s.model_prices)["gpt-5-mini"] == Price(0.25, 2.0)
    with pytest.raises(ValidationError, match="unknown price fields"):
        Settings(model_prices={"m": {"input": 1, "output": 2, "inptu": 3}})
    with pytest.raises(ValidationError, match="needs at least"):
        Settings(model_prices={"m": {"input": 1}})


# ------------------------------------------------------------------ metering


def test_meter_totals_and_unpriced_calls():
    with metering() as meter:
        usage.record(Usage("claude", "claude-haiku-4-5", "sql", 100, 10))
        usage.record(Usage("claude", "claude-haiku-4-5", "summary", 50, 5))
    assert meter.total("input_tokens") == 150
    assert meter.cost_usd == pytest.approx((150 * 1 + 15 * 5) / 1e6)
    with metering() as meter:
        usage.record(Usage("groq", "unpriced-model", "sql", 100, 10))
    assert meter.calls[0].cost_usd is None and meter.cost_usd is None


def test_record_outside_a_meter_does_nothing_and_meters_dont_mix():
    usage.record(Usage("claude", "claude-opus-5-5", "sql", 1, 1))  # no error, nowhere to go
    with metering() as outer:
        with metering() as inner:
            usage.record(Usage("local", "m", "sql", 1, 1))
        usage.record(Usage("local", "m", "summary", 2, 2))
    assert [c.purpose for c in inner.calls] == ["sql"]
    assert [c.purpose for c in outer.calls] == ["summary"]


# ------------------------------------------------------------------ generators


def test_claude_usage_is_priced_on_the_model_that_answered():
    # A server-side fallback can answer with another model than the one asked for.
    response = SimpleNamespace(
        model="claude-sonnet-5-5",
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text="```sql\nSELECT 1\n```")],
        usage=SimpleNamespace(
            input_tokens=120,
            output_tokens=80,
            cache_read_input_tokens=3000,
            cache_creation_input_tokens=0,
        ),
    )
    client = SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: response))
    )
    gen = ClaudeGenerator("SYSTEM", model="claude-opus-5-5", client=client)
    with metering() as meter:
        gen.generate("q")
    (call,) = meter.calls
    assert (call.model, call.purpose, call.cache_read_tokens) == ("claude-sonnet-5-5", "sql", 3000)
    assert call.cost_usd == pytest.approx((120 * 2 + 80 * 10 + 3000 * 0.2) / 1e6)


def test_hosted_usage_splits_out_cached_tokens_and_counts_empty_answers():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "model": "gpt-5-mini-2026",
                "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
                "usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 300,
                    "prompt_tokens_details": {"cached_tokens": 600},
                },
            },
        )

    gen = HostedGenerator(
        "SYSTEM", model="gpt-5-mini", base_url="https://example.test/v1", api_key="k",
        client=httpx.Client(transport=httpx.MockTransport(handler)), provider="openai",
    )  # fmt: skip
    with metering() as meter:
        with pytest.raises(Exception, match="empty answer"):
            gen.generate("q")
    (call,) = meter.calls  # the tokens were spent even though the answer was empty
    assert (call.input_tokens, call.cache_read_tokens, call.output_tokens) == (400, 600, 300)
    assert call.model == "gpt-5-mini-2026" and call.cost_usd is None  # no price configured


def test_local_model_usage_is_free():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "response": "<answer>```sql\nSELECT 1\n```</answer>",
                "prompt_eval_count": 900,
                "eval_count": 400,
            },
        )

    gen = LocalGenerator(
        dialect="sqlite", schema_ddl="", model="arctic", base_url="http://x", api="ollama",
        reference_date=None, client=httpx.Client(transport=httpx.MockTransport(handler)),
    )  # fmt: skip
    with metering() as meter:
        gen.generate("q")
    (call,) = meter.calls
    assert (call.input_tokens, call.output_tokens, call.cost_usd) == (900, 400, 0)


# ------------------------------------------------------------------ the API


class MeteredGenerator:
    """Writes the scripted SQL and reports usage the way the real generators do."""

    def __init__(self, *sqls):
        self.sqls, self.n = list(sqls), 0

    def generate(self, question, repairs=None):
        usage.record(Usage("claude", "claude-opus-5-5", "sql", 1000, 200))
        self.n += 1
        return Generation(self.sqls[self.n - 1], "")


@pytest.fixture
def records():
    """Log records from the API, captured directly (the askdb loggers don't propagate)."""
    got: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = got.append
    logger = logging.getLogger("askdb.api")
    logger.addHandler(handler)
    yield got
    logger.removeHandler(handler)


def _client(db_path, gen, **settings):
    registry = SourceRegistry(
        Settings(
            database_url=f"sqlite:///{db_path}",
            upload_dir=db_path.parent / "uploads",
            summaries="simple",
            **settings,
        )
    )
    db = registry.sample()
    db.generator_for = lambda *a, **k: gen
    app.dependency_overrides[get_registry] = lambda: registry
    return TestClient(app)


def _answers(records):
    return [r.fields for r in records if r.getMessage() == "answer"]


def test_each_answer_is_logged_and_its_usage_saved(db_path, store, records):
    client = _client(db_path, MeteredGenerator("SELECT countr FROM customer", "SELECT 1"))
    res = client.post("/api/ask", json={"question": "How many customers?", "provider": "claude"})
    assert res.status_code == 200
    (line,) = _answers(records)
    assert line["ok"] is True and line["attempts"] == 2 and line["calls"] == 2
    assert line["paid_by"] == "server" and line["input_tokens"] == 2000
    assert line["cost_usd"] == pytest.approx(2 * (1000 * 4 + 200 * 20) / 1e6)
    assert line["question"] is None  # questions stay out of logs by default
    (day,) = store.usage_report(1)
    assert (day["questions"], day["calls"], day["paid_by"]) == (1, 2, "server")
    requests = [r.fields for r in records if r.getMessage() == "request"]
    assert {"method": "POST", "path": "/api/ask", "status": 200}.items() <= requests[-1].items()


def test_failed_questions_still_count_what_they_spent(db_path, store, records):
    bad = "SELECT nope FROM nowhere"
    client = _client(db_path, MeteredGenerator(bad, bad, bad), log_questions=True)
    res = client.post(
        "/api/ask",
        json={"question": "x?", "provider": "claude"},
        headers={"X-AskDB-Api-Key": "users-own"},
    )
    assert res.status_code == 422
    (line,) = _answers(records)
    assert line["ok"] is False and line["error"] == "AnswerError" and line["attempts"] == 3
    assert line["paid_by"] == "user" and line["calls"] == 3 and line["question"] == "x?"
    assert store.usage_report(1)[0]["calls"] == 3


def test_streamed_answers_are_logged_after_they_finish(db_path, store, records):
    client = _client(db_path, MeteredGenerator("SELECT 1"))
    with client.stream(
        "POST", "/api/ask/stream", json={"question": "q", "provider": "claude"}
    ) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    assert events[-1]["type"] == "summary"
    (line,) = _answers(records)
    assert line["ok"] is True and line["calls"] == 1


def test_usage_tracking_can_be_turned_off(db_path, store):
    client = _client(db_path, MeteredGenerator("SELECT 1"), track_usage=False)
    client.post("/api/ask", json={"question": "q", "provider": "claude"})
    assert store.usage_report(1) == []


# ------------------------------------------------------------------ logs and the report


def _record(**fields):
    r = logging.LogRecord("askdb.api", logging.INFO, __file__, 1, "answer", None, None)
    r.fields = fields
    return r


def test_log_formats():
    line = json.loads(_JsonFormatter().format(_record(model="m", cost_usd=0.01, error=None)))
    assert line["event"] == "answer" and line["model"] == "m" and "error" not in line
    text = _TextFormatter().format(_record(path="/api/ask", note="two words"))
    assert text.endswith('answer path=/api/ask note="two words"')


def test_usage_report_command(store, monkeypatch, capsys):
    from askdb import cli

    store.add_usage(
        "q1", "server", [Usage("claude", "claude-opus-5-5", "sql", 1000, 200, 0, 0, 0.008)]
    )
    store.add_usage("q2", "user", [Usage("groq", "x", "sql", 10, 5, 0, 0, None)])
    monkeypatch.setattr("askdb.config.get_settings", lambda: SimpleNamespace(store_path=store.path))
    assert cli.main(["--usage", "1"]) == 0
    out = capsys.readouterr().out
    assert "claude-opus-5-5" in out and "$0.0080" in out and "unpriced" in out
    assert "Estimated spend on the server's keys, last 1 days: $0.0080" in out
