"""Stage 3, hosted variant: any OpenAI-compatible chat completions API.

Used by the "free" provider (Google Gemini's free tier by default) and by Groq,
OpenRouter and OpenAI (see askdb.providers). It uses the same prompt, few-shot
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
    build_summary_prompt,
    clean_summary,
    parse_response,
)
from askdb.prompts import SUMMARY_SYSTEM

# Some models (Qwen, gpt-oss, DeepSeek) put their reasoning in <think> tags.
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

# Where to get a key, per provider, for the "no key" message.
KEY_PAGES = {
    "free": ("a free Gemini key", "https://aistudio.google.com/apikey"),
    "groq": ("a Groq key (free tier available)", "https://console.groq.com/keys"),
    "openrouter": ("an OpenRouter key", "https://openrouter.ai/settings/keys"),
    "openai": ("an OpenAI key", "https://platform.openai.com/api-keys"),
}


def missing_key(provider: str) -> str:
    what, url = KEY_PAGES.get(provider, ("an API key", ""))
    env = f"ASKDB_{provider.upper()}_API_KEY"
    return (
        f"No API key for this provider. Get {what} at {url} and add it under API keys "
        f"(the key button at the top of the page), or set {env} on the server."
    )


MISSING_KEY = missing_key("free")


def _headers(api_key: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


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
        provider: str = "free",
        label: str = "free model",
    ):
        self.system_prompt = system_prompt
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.context = context or []
        self.provider = provider
        self.label = label  # how errors name the provider: "free model", "Groq", ...
        self.max_tokens = max_tokens  # thinking models count reasoning against this
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=timeout_s)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def generate(self, question: str, repairs: list[Repair] | None = None) -> Generation:
        messages = [{"role": "system", "content": self.system_prompt}]
        messages += build_messages(question, repairs, self.context)
        return parse_response(self._chat(messages))

    def summarize(
        self, question: str, columns: list[str], rows: list[list], truncated: bool
    ) -> str:
        """One or two sentences answering the question from the result."""
        prompt = build_summary_prompt(question, columns, rows, truncated)
        messages = [
            {"role": "system", "content": SUMMARY_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        return clean_summary(self._chat(messages, temperature=0.2))

    def _chat(self, messages: list[dict], temperature: float = 0) -> str:
        """The text of one chat completion, without any <think> reasoning."""
        if not self.api_key:
            raise GenerationError(missing_key(self.provider))
        try:
            res = self.client.post(
                f"{self.base_url}/chat/completions",
                headers=_headers(self.api_key),
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": self.max_tokens,
                },
            )
        except httpx.ConnectError as e:
            raise GenerationError(f"Cannot reach the {self.label} API at {self.base_url}.") from e
        except httpx.TimeoutException as e:
            raise GenerationError(f"The {self.label} took too long to answer. Try again.") from e

        if res.status_code >= 400:
            raise GenerationError(self._explain(res))
        try:
            choice = res.json()["choices"][0]
            text = choice["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise GenerationError(f"The {self.label} returned an unexpected response.") from e
        if not text.strip():
            reason = choice.get("finish_reason") or "no text"
            raise GenerationError(f"The {self.label} returned an empty answer ({reason}).")
        return _THINK.sub("", text)

    def _explain(self, res: httpx.Response) -> str:
        detail = error_detail(res)
        # Gemini answers 400 (not 401) for a bad key.
        bad_key = res.status_code == 400 and "api key" in detail.lower()
        if res.status_code in (401, 403) or bad_key:
            return f"The {self.label} API rejected the key (HTTP {res.status_code}): {detail}"
        if res.status_code == 404:
            return (
                f"Model “{self.model}” not found: {detail}. Pick another model in the model "
                "menu, or run `uv run askdb --list-models` to see what your key can use."
            )
        if res.status_code == 429:
            return f"The {self.label} hit its rate limit. Wait a minute and try again. ({detail})"
        return f"{self.label} API error {res.status_code}: {detail}"
