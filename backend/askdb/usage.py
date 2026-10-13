"""Token usage and cost of model calls.

Generators report each call's usage with `record()`. Whatever is running the
pipeline opens a `metering()` block around a question (its SQL attempts and its
summary), and reads the calls and totals from the meter afterwards, for the log
line and the usage table. Outside a metering block, `record()` does nothing.

Costs are estimates from per-million-token prices. Claude's are built in (see
CLAUDE_PRICES); the open model on your own machine and the "free" provider cost
nothing; other models are priced only if the operator sets ASKDB_MODEL_PRICES.
A call with no known price has `cost_usd = None`: its tokens still count.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Price:
    """US dollars per million tokens."""

    input: float
    output: float
    cache_read: float | None = None  # None: same as input
    cache_write: float | None = None  # None: 1.25x input (the 5-minute cache)

    def cost(self, u: Usage) -> float:
        read = self.input if self.cache_read is None else self.cache_read
        write = self.input * 1.25 if self.cache_write is None else self.cache_write
        return (
            u.input_tokens * self.input
            + u.output_tokens * self.output
            + u.cache_read_tokens * read
            + u.cache_write_tokens * write
        ) / 1_000_000


# Anthropic's first-party API prices for the models AskDB offers, as of
# 2026-10-06. Thinking is billed as output. Override or extend with
# ASKDB_MODEL_PRICES when prices change.
CLAUDE_PRICES: dict[str, Price] = {
    "claude-fable-5-1": Price(10.00, 50.00, cache_read=0.25),
    "claude-opus-5-5": Price(4.00, 20.00, cache_read=0.20),
    "claude-sonnet-5-5": Price(2.00, 10.00, cache_read=0.20),
    "claude-haiku-4-5": Price(1.00, 5.00, cache_read=0.10),
}
# Providers whose calls cost nothing: the open model runs on your own machine,
# and the "free" provider is Gemini's free tier by default (set a price in
# ASKDB_MODEL_PRICES if you point it at a paid API).
FREE_PROVIDERS = frozenset({"local", "free"})


@dataclass
class Usage:
    """One model call."""

    provider: str
    model: str  # the model that answered (a Claude fallback can differ from the one asked)
    purpose: str  # "sql" or "summary"
    input_tokens: int = 0  # uncached input
    output_tokens: int = 0  # includes thinking
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float | None = None

    @property
    def tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
        )


def price_for(provider: str, model: str, overrides: dict[str, Price] | None = None) -> Price | None:
    """The price of a model, or None if it isn't known. Operator overrides win."""
    if overrides and model in overrides:
        return overrides[model]
    if provider in FREE_PROVIDERS:
        return Price(0, 0)
    if provider == "claude":
        return CLAUDE_PRICES.get(model)
    return None


def parse_prices(raw: dict[str, dict[str, float]]) -> dict[str, Price]:
    """ASKDB_MODEL_PRICES: {"model-id": {"input": 0.5, "output": 1.5, ...}}, per
    million tokens; `cache_read` and `cache_write` are optional."""
    return {model: Price(**fields) for model, fields in raw.items()}


@dataclass
class Meter:
    """The model calls made for one question."""

    prices: dict[str, Price] = field(default_factory=dict)
    calls: list[Usage] = field(default_factory=list)

    def add(self, u: Usage) -> None:
        price = price_for(u.provider, u.model, self.prices)
        u.cost_usd = price.cost(u) if price else None
        self.calls.append(u)

    @property
    def cost_usd(self) -> float | None:
        """Total cost, or None if any call couldn't be priced."""
        costs = [c.cost_usd for c in self.calls]
        return None if any(c is None for c in costs) else sum(costs)  # type: ignore[arg-type]

    def total(self, attr: str) -> int:
        return sum(getattr(c, attr) for c in self.calls)


_current: contextvars.ContextVar[Meter | None] = contextvars.ContextVar("askdb_meter", default=None)


@contextmanager
def metering(prices: dict[str, Price] | None = None) -> Iterator[Meter]:
    """Collect the usage of every model call made inside the block."""
    meter = Meter(prices or {})
    token = _current.set(meter)
    try:
        yield meter
    finally:
        _current.reset(token)


def record(usage: Usage) -> None:
    """Report one model call to the current meter, if there is one."""
    meter = _current.get()
    if meter is not None:
        meter.add(usage)


def _int(value: object) -> int:
    return value if isinstance(value, int) else 0


def from_anthropic(response: object, provider: str, model: str, purpose: str) -> Usage:
    """Usage from a Messages API response. `input_tokens` there is already the
    uncached remainder; cache reads and writes are separate fields."""
    u = getattr(response, "usage", None)
    return Usage(
        provider=provider,
        model=str(getattr(response, "model", None) or model),
        purpose=purpose,
        input_tokens=_int(getattr(u, "input_tokens", 0)),
        output_tokens=_int(getattr(u, "output_tokens", 0)),
        cache_read_tokens=_int(getattr(u, "cache_read_input_tokens", 0)),
        cache_write_tokens=_int(getattr(u, "cache_creation_input_tokens", 0)),
    )


def from_openai(body: dict, provider: str, model: str, purpose: str) -> Usage:
    """Usage from an OpenAI-compatible chat or completions response. There,
    cached tokens are part of prompt_tokens, so they're split out."""
    u = body.get("usage") or {}
    prompt = _int(u.get("prompt_tokens"))
    cached = _int((u.get("prompt_tokens_details") or {}).get("cached_tokens"))
    return Usage(
        provider=provider,
        model=str(body.get("model") or model),
        purpose=purpose,
        input_tokens=max(prompt - cached, 0),
        output_tokens=_int(u.get("completion_tokens")),
        cache_read_tokens=cached,
    )
