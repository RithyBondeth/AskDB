"""Model choice: who may pick which model, and the lists the picker shows."""

import json

import anthropic
import httpx
import httpx2
import pytest

from askdb import providers
from askdb.config import Settings
from askdb.generate import ClaudeGenerator
from askdb.hosted import HostedGenerator
from askdb.pipeline import AskDB
from askdb.providers import ModelNotAllowed, list_models, resolve_model


@pytest.fixture(autouse=True)
def fresh_cache():
    providers.clear_cache()
    yield
    providers.clear_cache()


def settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


# ------------------------------------------------------------------ resolve_model


def test_no_model_means_the_provider_default():
    s = settings(groq_model="g-default")
    assert resolve_model(s, "groq", None, None) == "g-default"
    assert resolve_model(s, "claude", None, None) == "claude-opus-5-5"
    assert resolve_model(s, "local", "", None) == s.local_model


def test_rejects_malformed_names():
    for bad in ("../etc", "a b", "x" * 300, "-flag", "m\nn"):
        with pytest.raises(ModelNotAllowed, match="valid"):
            resolve_model(settings(), "groq", bad, "user-key")


def test_server_key_only_allows_the_operators_list():
    s = settings(groq_model="small", groq_models=["small", "medium"])
    assert resolve_model(s, "groq", "medium", None) == "medium"
    with pytest.raises(ModelNotAllowed, match="own API key"):
        resolve_model(s, "groq", "huge", None)
    # The user's own key pays, so anything goes.
    assert resolve_model(s, "groq", "huge", "user-key") == "huge"


def test_claude_models_come_from_askdbs_catalog():
    s = settings()
    assert resolve_model(s, "claude", "claude-haiku-4-5", None) == "claude-haiku-4-5"
    # Fable costs more than the default, so the server's key doesn't offer it...
    with pytest.raises(ModelNotAllowed, match="own API key"):
        resolve_model(s, "claude", "claude-fable-5-1", None)
    # ...but a user's own key may use it.
    assert resolve_model(s, "claude", "claude-fable-5-1", "k") == "claude-fable-5-1"
    # Models AskDB doesn't know how to call are refused even with a key.
    with pytest.raises(ModelNotAllowed, match="supports these Claude models"):
        resolve_model(s, "claude", "claude-opus-4-1", "k")


def test_local_accepts_any_well_formed_model():
    assert resolve_model(settings(), "local", "qwen3:8b", None) == "qwen3:8b"


# ------------------------------------------------------------------ list_models


def test_claude_list_depends_on_whose_key():
    s = settings()
    server = [m["id"] for m in list_models(s, "claude", None).models]
    own = [m["id"] for m in list_models(s, "claude", "k").models]
    assert "claude-fable-5-1" not in server and "claude-haiku-4-5" in server
    assert own == [m.id for m in providers.CLAUDE_MODELS]


def test_hosted_without_user_key_lists_only_allowed_models(monkeypatch):
    monkeypatch.setattr(providers, "fetch_hosted_models", pytest.fail)  # no network call
    result = list_models(settings(groq_models=["a", "b"]), "groq", None)
    assert [m["id"] for m in result.models] == ["openai/gpt-oss-120b", "a", "b"]
    assert result.source == "allowed"


def test_hosted_with_user_key_lists_live_and_caches(monkeypatch):
    calls = []

    def fake(base_url, key):
        calls.append((base_url, key))
        return ["gpt-5-mini", "gpt-image-1", "text-embedding-3-small", "o4-mini", "whisper-1"]

    monkeypatch.setattr(providers, "fetch_hosted_models", fake)
    s = settings()
    result = list_models(s, "openai", "sk-user")
    assert [m["id"] for m in result.models] == ["gpt-5-mini", "o4-mini"]  # chat models only
    assert result.source == "live" and result.default == "gpt-5-mini"
    list_models(s, "openai", "sk-user")
    assert calls == [("https://api.openai.com/v1", "sk-user")]  # second call cached


def test_default_falls_back_to_first_model_the_key_has(monkeypatch):
    monkeypatch.setattr(providers, "fetch_hosted_models", lambda url, key: ["m1", "m2"])
    result = list_models(settings(groq_model="gone"), "groq", "k")
    assert result.default == "m1"


def test_gemini_list_drops_embedding_models(monkeypatch):
    monkeypatch.setattr(
        providers,
        "fetch_hosted_models",
        lambda url, key: ["gemini-flash-latest", "gemini-embedding-001", "imagen-4", "gemma-3"],
    )
    ids = [m["id"] for m in list_models(settings(), "free", "k").models]
    assert ids == ["gemini-flash-latest"]


def test_rejected_key_is_reported(monkeypatch):
    def rejected(url, key):
        req = httpx.Request("GET", url)
        raise httpx.HTTPStatusError("no", request=req, response=httpx.Response(401, request=req))

    monkeypatch.setattr(providers, "fetch_hosted_models", rejected)
    result = list_models(settings(), "groq", "bad")
    assert result.error == "Groq rejected the key."
    assert [m["id"] for m in result.models] == ["openai/gpt-oss-120b"]


def test_local_lists_installed_ollama_models():
    def handler(req):
        assert req.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "b:7b"}, {"name": "a:1b"}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert providers.fetch_local_models("http://ollama", "ollama", client) == ["a:1b", "b:7b"]


def test_local_unreachable_still_offers_the_default():
    result = list_models(settings(local_base_url="http://127.0.0.1:9"), "local", None)
    assert result.error and "Couldn't reach" in result.error
    assert [m["id"] for m in result.models] == [settings().local_model]


# ------------------------------------------------------------------ generators


def test_groq_generator_uses_groq_url_key_and_model(db_path):
    s = settings(database_url=f"sqlite:///{db_path}", groq_api_key="server-groq")
    gen = AskDB.from_settings(s).generator_for("q", provider="groq", model="llama-x")
    assert isinstance(gen, HostedGenerator)
    assert (gen.base_url, gen.api_key, gen.model) == (
        "https://api.groq.com/openai/v1",
        "server-groq",
        "llama-x",
    )
    assert "Groq" in gen._explain(httpx.Response(500, text="boom"))
    gen.close()


def _claude_body(model: str) -> dict:
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx2.Response(
            200,
            json={
                "id": "m",
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [{"type": "text", "text": "```sql\nSELECT 1\n```"}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    client = anthropic.Anthropic(
        api_key="k", http_client=httpx2.Client(transport=httpx2.MockTransport(handler))
    )
    ClaudeGenerator("S", model=model, client=client).generate("q")
    return seen[0]


def test_claude_request_options_fit_each_model():
    for model in ("claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1"):
        body = _claude_body(model)
        assert body["model"] == model
        assert body["thinking"] == {"type": "adaptive"}
        assert body["output_config"] == {"effort": "medium"}
    # Haiku 4.5 rejects adaptive thinking and effort.
    haiku = _claude_body("claude-haiku-4-5")
    assert "thinking" not in haiku and "output_config" not in haiku and "fallbacks" not in haiku


def test_cache_stays_bounded(monkeypatch):
    monkeypatch.setattr(providers, "_CACHE_MAX", 10)
    for i in range(25):
        providers._cached(f"k{i}", lambda: ["m"])
    assert len(providers._cache) <= 10
    assert "k24" in providers._cache  # the newest entry is kept


# ------------------------------------------------------------------ eval scores


def _result(path, provider, model, hits, total=35, seconds=2.0):
    import json as _json

    path.write_text(
        _json.dumps(
            {
                "provider": provider,
                "model": model,
                "accuracy": hits / total,
                "hits": hits,
                "total": total,
                "median_seconds": seconds,
                "results": [],
            }
        )
    )


def test_menu_shows_eval_scores_and_recommends_the_best(tmp_path):
    _result(tmp_path / "opus.json", "claude", "claude-opus-5-5", 31)
    _result(tmp_path / "haiku.json", "claude", "claude-haiku-4-5", 27)
    _result(tmp_path / "smoke.json", "claude", "claude-sonnet-5-5", 5, total=5)  # --limit run
    (tmp_path / "notes.json").write_text("{}")  # not a results file
    s = settings(eval_results_dir=tmp_path)
    models = {m["id"]: m for m in list_models(s, "claude", None).models}
    assert models["claude-opus-5-5"]["score"] == "89% on eval"
    assert models["claude-opus-5-5"].get("recommended") is True
    assert models["claude-haiku-4-5"]["score"] == "77% on eval"
    assert "recommended" not in models["claude-haiku-4-5"]
    assert "score" not in models["claude-sonnet-5-5"]  # smoke runs don't count


def test_newest_run_wins_and_ties_go_to_the_faster_model(tmp_path):
    import os

    _result(tmp_path / "a-old.json", "groq", "fast", 20, seconds=1.0)
    _result(tmp_path / "b-new.json", "groq", "fast", 30, seconds=1.0)
    os.utime(tmp_path / "a-old.json", (1, 1))
    _result(tmp_path / "slow.json", "groq", "slow", 30, seconds=9.0)
    s = settings(eval_results_dir=tmp_path, groq_models=["fast", "slow"])
    models = {m["id"]: m for m in list_models(s, "groq", None).models}
    assert models["fast"]["score"] == "86% on eval"
    assert models["fast"].get("recommended") and not models["slow"].get("recommended")


def test_no_results_means_no_labels(tmp_path):
    s = settings(eval_results_dir=tmp_path / "missing")
    assert all("score" not in m for m in list_models(s, "claude", "k").models)
