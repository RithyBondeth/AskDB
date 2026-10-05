"""The model providers AskDB can use, which models each offers, and who may pick what.

Three kinds of provider:

- ``claude``: Anthropic's API, with a curated list of models (request options
  differ per model, see ``ClaudeGenerator``).
- hosted: any OpenAI-compatible chat API. ``free`` (Gemini's free tier by
  default), Groq, OpenRouter and OpenAI. Their model lists come live from the
  provider's ``/models`` endpoint.
- ``local``: an open model on the server's own machine (Ollama by default).

Who may pick which model matters because of cost. When a visitor uses their own
key, they pay, so any model the provider offers is fine. When the server's key
pays, visitors may only pick models the operator allowed (``ASKDB_*_MODELS``).
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
from dataclasses import dataclass
from typing import Literal, get_args

import httpx

from askdb.config import Settings
from askdb.scores import annotate, load_scores

Provider = Literal["claude", "free", "groq", "openrouter", "openai", "local"]
PROVIDERS: tuple[Provider, ...] = get_args(Provider)
HOSTED: tuple[Provider, ...] = ("free", "groq", "openrouter", "openai")

# Model ids are passed to provider APIs, so keep them to the characters real ids use.
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$")


@dataclass(frozen=True)
class ClaudeModel:
    id: str
    label: str
    note: str


# Request options differ per model (see ClaudeGenerator), so only models AskDB
# knows how to call are offered, even to users with their own key.
CLAUDE_MODELS: tuple[ClaudeModel, ...] = (
    ClaudeModel("claude-opus-5-5", "Claude Opus 5.5", "best balance (default)"),
    ClaudeModel("claude-sonnet-5-5", "Claude Sonnet 5.5", "faster, half the price of Opus"),
    ClaudeModel("claude-haiku-4-5", "Claude Haiku 4.5", "fastest and cheapest"),
    ClaudeModel("claude-fable-5-1", "Claude Fable 5.1", "most capable, 2.5x the price of Opus"),
)
CLAUDE_MODEL_IDS = frozenset(m.id for m in CLAUDE_MODELS)


@dataclass(frozen=True)
class HostedConfig:
    """Where a hosted provider lives and what the server allows on its key."""

    label: str
    base_url: str
    api_key: str | None
    default: str
    allowed: list[str]  # with the server's key


class ModelNotAllowed(ValueError):
    """The requested model isn't available to this request. The message is for the user."""


def hosted_config(settings: Settings, provider: Provider) -> HostedConfig:
    def key(name: str) -> str | None:
        secret = getattr(settings, f"{name}_api_key")
        return secret.get_secret_value() if secret else None

    labels = {"free": "free model", "groq": "Groq", "openrouter": "OpenRouter", "openai": "OpenAI"}
    default = getattr(settings, f"{provider}_model")
    allowed = list(getattr(settings, f"{provider}_models")) or [default]
    return HostedConfig(
        label=labels[provider],
        base_url=getattr(settings, f"{provider}_base_url").rstrip("/"),
        api_key=key(provider),
        default=default,
        allowed=allowed if default in allowed else [default, *allowed],
    )


def default_model(settings: Settings, provider: Provider) -> str:
    if provider == "claude":
        return settings.model
    if provider == "local":
        return settings.local_model
    return hosted_config(settings, provider).default


def server_claude_models(settings: Settings) -> list[str]:
    """Claude models visitors may use on the server's key: the allowlist plus the default."""
    allowed = [m for m in settings.claude_models if m in CLAUDE_MODEL_IDS]
    return allowed if settings.model in allowed else [settings.model, *allowed]


def resolve_model(
    settings: Settings, provider: Provider, model: str | None, user_key: str | None
) -> str:
    """The model to use for a request, or ModelNotAllowed explaining why not."""
    if not model:
        return default_model(settings, provider)
    if not _MODEL_ID.match(model):
        raise ModelNotAllowed("That isn't a valid model name.")
    if provider == "local":
        return model  # the server's own machine; only installed models can run
    if provider == "claude":
        if model not in CLAUDE_MODEL_IDS:
            names = ", ".join(m.id for m in CLAUDE_MODELS)
            raise ModelNotAllowed(f"AskDB supports these Claude models: {names}.")
        allowed = None if user_key else server_claude_models(settings)
    else:
        allowed = None if user_key else hosted_config(settings, provider).allowed
    if allowed is not None and model not in allowed:
        raise ModelNotAllowed(
            f"“{model}” needs your own API key (add one under API keys). "
            f"With the server's key you can use: {', '.join(allowed)}."
        )
    return model


# ------------------------------------------------------------------ listing


@dataclass
class ModelList:
    default: str
    models: list[dict]  # {"id", "label", "note"?}
    # "live": fetched from the provider; "allowed": the server's allowlist;
    # "catalog": AskDB's own list.
    source: Literal["live", "allowed", "catalog"]
    error: str | None = None


# Live lists are cached briefly so opening the menu doesn't call the provider each time.
# Entries are per user key, so the cache is capped for busy public servers.
_CACHE_TTL_S = 600
_CACHE_MAX = 500
_cache: dict[str, tuple[float, list[str]]] = {}
_cache_lock = threading.Lock()


def _cached(key: str, fetch) -> list[str]:
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < _CACHE_TTL_S:
            return hit[1]
    value = fetch()
    with _cache_lock:
        if len(_cache) >= _CACHE_MAX:
            expired = [k for k, (t, _) in _cache.items() if now - t >= _CACHE_TTL_S]
            for k in expired or list(_cache)[: _CACHE_MAX // 2]:  # oldest first
                del _cache[k]
        _cache[key] = (now, value)
    return value


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


# OpenAI's /models also lists embedding, audio, image and moderation models.
_OPENAI_CHAT = re.compile(r"^(gpt-|o\d|chatgpt-)")
_OPENAI_NOT_CHAT = re.compile(
    r"audio|realtime|tts|transcribe|image|search|embedding|instruct|moderation|codex"
)


def _chat_models(provider: Provider, ids: list[str]) -> list[str]:
    if provider == "openai":
        return [m for m in ids if _OPENAI_CHAT.match(m) and not _OPENAI_NOT_CHAT.search(m)]
    if provider == "free" and any(m.startswith("gemini") for m in ids):
        # Gemini also lists embedding and image models.
        return [m for m in ids if m.startswith("gemini") and "embedding" not in m]
    return ids


def fetch_hosted_models(
    base_url: str, api_key: str | None, client: httpx.Client | None = None
) -> list[str]:
    """Model ids an OpenAI-compatible endpoint offers this key (GET /models)."""
    if client is None:
        with httpx.Client(timeout=15) as own:
            return fetch_hosted_models(base_url, api_key, own)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    res = client.get(f"{base_url.rstrip('/')}/models", headers=headers)
    res.raise_for_status()
    ids = [m.get("id", "") for m in res.json().get("data", [])]
    # Gemini prefixes ids with "models/"; the chat endpoint accepts them without it.
    return sorted({i.removeprefix("models/") for i in ids if i})


def fetch_local_models(
    base_url: str, api: Literal["ollama", "openai"], client: httpx.Client | None = None
) -> list[str]:
    """Models installed on the local server (Ollama's /api/tags, or /v1/models)."""
    if client is None:
        with httpx.Client(timeout=5) as own:
            return fetch_local_models(base_url, api, own)
    base = base_url.rstrip("/")
    if api == "openai":
        return fetch_hosted_models(f"{base}/v1", None, client)
    res = client.get(f"{base}/api/tags")
    res.raise_for_status()
    return sorted(m["name"] for m in res.json().get("models", []) if m.get("name"))


def _entries(default: str, ids: list[str]) -> list[dict]:
    """Picker entries for these ids, with the default always among them."""
    return [{"id": m, "label": m} for m in (ids if default in ids else [default, *ids])]


def list_models(settings: Settings, provider: Provider, user_key: str | None) -> ModelList:
    """The models to offer in the picker for this provider and request, with eval
    scores on the models that have been measured (see askdb.scores)."""
    result = _list_models(settings, provider, user_key)
    annotate(provider, result.models, load_scores(settings.eval_results_dir))
    return result


def _list_models(settings: Settings, provider: Provider, user_key: str | None) -> ModelList:
    if provider == "claude":
        allowed = CLAUDE_MODEL_IDS if user_key else set(server_claude_models(settings))
        return ModelList(
            default=settings.model,
            models=[
                {"id": m.id, "label": m.label, "note": m.note}
                for m in CLAUDE_MODELS
                if m.id in allowed
            ],
            source="catalog",
        )

    if provider == "local":
        default = settings.local_model
        try:
            ids = _cached(
                f"local:{settings.local_base_url}",
                lambda: fetch_local_models(settings.local_base_url, settings.local_api),
            )
        except httpx.HTTPError:
            return ModelList(
                default,
                _entries(default, []),
                "allowed",
                error=f"Couldn't reach the local model server at {settings.local_base_url}.",
            )
        return ModelList(default, _entries(default, ids), "live")

    cfg = hosted_config(settings, provider)
    if not user_key:
        return ModelList(cfg.default, _entries(cfg.default, cfg.allowed), "allowed")
    digest = hashlib.sha256(f"{provider}\0{cfg.base_url}\0{user_key}".encode()).hexdigest()
    try:
        ids = _cached(f"hosted:{digest}", lambda: fetch_hosted_models(cfg.base_url, user_key))
    except httpx.HTTPStatusError as e:
        bad_key = e.response.status_code in (400, 401, 403)
        return ModelList(
            cfg.default,
            _entries(cfg.default, []),
            "allowed",
            error=f"{cfg.label} rejected the key."
            if bad_key
            else f"{cfg.label} returned HTTP {e.response.status_code}.",
        )
    except httpx.HTTPError:
        return ModelList(
            cfg.default,
            _entries(cfg.default, []),
            "allowed",
            error=f"Couldn't reach {cfg.label}.",
        )
    ids = _chat_models(provider, ids)
    # Prefer the configured default; if this key can't use it, start on the first one.
    default = cfg.default if cfg.default in ids or not ids else ids[0]
    return ModelList(default, _entries(default, ids), "live")
