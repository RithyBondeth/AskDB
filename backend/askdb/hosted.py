"""Stage 3, hosted variant: any OpenAI-compatible chat completions API.

Meant for free testing without an Anthropic key. The default is Google Gemini's
free tier; Groq, OpenRouter (":free" models), Hugging Face, LM Studio, and others
work by changing the base URL, key, and model. It uses the same prompt, few-shot
examples, follow-up context, and error-feedback turns as the Claude generator.
"""

from __future__ import annotations

import re

import httpx

from askdb.generate import (
    Generation,
    GenerationError,
    Repair,
    Turn,
    build_messages,
    parse_response,
)

# Some models (Qwen, gpt-oss, DeepSeek) put their reasoning in <think> tags.
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

MISSING_KEY = (
    "No API key for the free model. Get a free Gemini key at "
    "https://aistudio.google.com/apikey and add it under API keys (the key button "
    "at the top of the page), or set ASKDB_FREE_API_KEY on the server."
)


def _headers(api_key: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def list_models(
    base_url: str, api_key: str | None, client: httpx.Client | None = None
) -> list[str]:
    """Model IDs the endpoint offers (GET /models), to find a valid ASKDB_FREE_MODEL."""
    if client is None:
        with httpx.Client(timeout=30) as own:
            return list_models(base_url, api_key, own)
    res = client.get(f"{base_url.rstrip('/')}/models", headers=_headers(api_key))
    res.raise_for_status()
    ids = [m.get("id", "") for m in res.json().get("data", [])]
    # Gemini prefixes ids with "models/"; the chat endpoint accepts them without it.
    return sorted(i.removeprefix("models/") for i in ids if i)


def error_detail(res: httpx.Response) -> str:
    """The provider's error message, from the usual JSON shapes, or the raw text."""
    detail = res.text[:300]
    try:
        body = res.json()
        body = body[0] if isinstance(body, list) and body else body
        err = body.get("error", body) if isinstance(body, dict) else body
        detail = err.get("message", detail) if isinstance(err, dict) else str(err)
    except ValueError:
        pass
    return str(detail)


class HostedGenerator:
    """Generates SQL with an OpenAI-compatible chat completions API."""

    def __init__(
        self,
        system_prompt: str,
        model: str,
        base_url: str,
        api_key: str | None,
        context: list[Turn] | None = None,
        timeout_s: float = 120.0,
        max_tokens: int = 8192,
        client: httpx.Client | None = None,
    ):
        self.system_prompt = system_prompt
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.context = context or []
        self.max_tokens = max_tokens  # thinking models count reasoning against this
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=timeout_s)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def generate(self, question: str, repairs: list[Repair] | None = None) -> Generation:
        if not self.api_key:
            raise GenerationError(MISSING_KEY)
        messages = [{"role": "system", "content": self.system_prompt}]
        messages += build_messages(question, repairs, self.context)
        try:
            res = self.client.post(
                f"{self.base_url}/chat/completions",
                headers=_headers(self.api_key),
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0,
                    "max_tokens": self.max_tokens,
                },
            )
        except httpx.ConnectError as e:
            raise GenerationError(f"Cannot reach the free model API at {self.base_url}.") from e
        except httpx.TimeoutException as e:
            raise GenerationError("The free model took too long to answer. Try again.") from e

        if res.status_code >= 400:
            raise GenerationError(self._explain(res))
        try:
            choice = res.json()["choices"][0]
            text = choice["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise GenerationError("The free model returned an unexpected response.") from e
        if not text.strip():
            reason = choice.get("finish_reason") or "no text"
            raise GenerationError(f"The free model returned an empty answer ({reason}).")
        return parse_response(_THINK.sub("", text))

    def _explain(self, res: httpx.Response) -> str:
        detail = error_detail(res)
        # Gemini answers 400 (not 401) for a bad key.
        bad_key = res.status_code == 400 and "api key" in detail.lower()
        if res.status_code in (401, 403) or bad_key:
            return f"The free model API rejected the key (HTTP {res.status_code}): {detail}"
        if res.status_code == 404:
            return (
                f"Model “{self.model}” not found: {detail}. Run `uv run askdb --list-models` "
                "to see the models your key can use, then set ASKDB_FREE_MODEL."
            )
        if res.status_code == 429:
            return f"Free-tier rate limit reached. Wait a minute and try again. ({detail})"
        return f"Free model API error {res.status_code}: {detail}"
