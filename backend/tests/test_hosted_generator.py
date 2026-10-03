"""The free-model generator (OpenAI-compatible chat API), against mock servers."""

import json

import httpx
import pytest

from askdb.config import Settings
from askdb.execute import answer
from askdb.generate import GenerationError, Repair, Turn
from askdb.hosted import HostedGenerator, list_models
from askdb.pipeline import AskDB


def mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def reply(text, finish="stop"):
    return httpx.Response(
        200,
        json={
            "choices": [
                {"message": {"role": "assistant", "content": text}, "finish_reason": finish}
            ]
        },
    )


def make(handler, **kw):
    return HostedGenerator(
        "SYSTEM PROMPT",
        model="gemini-flash-latest",
        base_url="https://example.test/v1beta/openai/",
        api_key=kw.pop("api_key", "secret"),
        client=mock_client(handler),
        **kw,
    )


def test_request_shape_and_parse():
    seen = []

    def handler(req):
        seen.append(req)
        return reply("```sql\nSELECT 1\n```\nReturns one.")

    gen = make(handler, context=[Turn("earlier q", "SELECT 0")]).generate(
        "q", [Repair("SELECT x", "no such column: x")]
    )
    assert gen.sql == "SELECT 1" and gen.explanation == "Returns one."
    req = seen[0]
    assert str(req.url) == "https://example.test/v1beta/openai/chat/completions"
    assert req.headers["authorization"] == "Bearer secret"
    body = json.loads(req.content)
    assert body["model"] == "gemini-flash-latest" and body["temperature"] == 0
    roles = [m["role"] for m in body["messages"]]
    # system, earlier turn (user/assistant), question, failed attempt, repair request
    assert roles == ["system", "user", "assistant", "user", "assistant", "user"]
    assert body["messages"][0]["content"] == "SYSTEM PROMPT"
    assert "no such column: x" in body["messages"][-1]["content"]


def test_strips_think_tags():
    gen = make(lambda r: reply("<think>```sql\nSELECT wrong\n```</think>```sql\nSELECT 2\n```"))
    assert gen.generate("q").sql == "SELECT 2"


def test_missing_key_explains_where_to_get_one():
    with pytest.raises(GenerationError, match="aistudio.google.com"):
        make(lambda r: reply(""), api_key=None).generate("q")


@pytest.mark.parametrize(
    ("status", "body", "match"),
    [
        (401, {"error": {"message": "API key not valid"}}, "rejected the key"),
        (400, [{"error": {"message": "Please pass a valid API key"}}], "rejected the key"),
        (404, [{"error": {"message": "model not found"}}], "--list-models"),
        (429, {"error": {"message": "quota"}}, "rate limit"),
        (500, "boom", "error 500"),
    ],
)
def test_http_errors_are_explained(status, body, match):
    gen = make(lambda r: httpx.Response(status, json=body))
    with pytest.raises(GenerationError, match=match):
        gen.generate("q")


def test_empty_answer_is_an_error():
    with pytest.raises(GenerationError, match="empty answer"):
        make(lambda r: reply(None, finish="length")).generate("q")


def test_unreachable_server():
    def handler(req):
        raise httpx.ConnectError("refused")

    with pytest.raises(GenerationError, match="Cannot reach"):
        make(handler).generate("q")


def test_self_correction_with_free_model(engine):
    replies = iter(
        ["```sql\nSELECT nme FROM customer\n```", "```sql\nSELECT name FROM customer\n```"]
    )
    ans = answer("names?", make(lambda r: reply(next(replies))), engine, "sqlite")
    assert len(ans.attempts) == 2 and len(ans.result.rows) == 3


def test_list_models_strips_gemini_prefix():
    def handler(req):
        assert req.url.path.endswith("/models")
        return httpx.Response(200, json={"data": [{"id": "models/gemini-b"}, {"id": "gemini-a"}]})

    assert list_models("https://x.test/v1", "k", mock_client(handler)) == ["gemini-a", "gemini-b"]


def settings(db_path, **kw):
    base = {
        "database_url": f"sqlite:///{db_path}",
        "anthropic_api_key": None,
        "free_api_key": None,
        "provider": "auto",
    }
    return Settings(**(base | kw))


def test_free_is_the_default_provider(db_path, monkeypatch):
    monkeypatch.delenv("ASKDB_PROVIDER", raising=False)
    s = Settings(database_url=f"sqlite:///{db_path}", _env_file=None)
    assert s.provider == "free"
    db = AskDB.from_settings(s)
    assert db.default_provider == "free"
    assert db.model_name() == "gemini-flash-latest"


def test_auto_provider(db_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert AskDB.from_settings(settings(db_path)).default_provider == "free"
    free = AskDB.from_settings(settings(db_path, free_api_key="k"))
    assert free.default_provider == "free" and free.configured["free"]
    both = AskDB.from_settings(settings(db_path, free_api_key="k", anthropic_api_key="a"))
    assert both.default_provider == "claude"
    forced = AskDB.from_settings(settings(db_path, provider="local", anthropic_api_key="a"))
    assert forced.default_provider == "local"


def test_free_generator_gets_the_full_prompt(db_path):
    db = AskDB.from_settings(settings(db_path, free_api_key="k", free_model="some-model"))
    gen = db.generator_for("how many customers", provider="free")
    assert isinstance(gen, HostedGenerator)
    assert gen.model == "some-model" and gen.api_key == "k"
    assert "CREATE TABLE customer" in gen.system_prompt
    assert db.model_name("free") == "some-model"
