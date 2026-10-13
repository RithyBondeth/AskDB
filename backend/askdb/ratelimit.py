"""Per-client request limits, kept in memory.

A public AskDB spends the operator's model key and disk on every visitor, so
asking, running SQL, uploading and checking keys are each limited per client IP.

Client IPs come from X-Forwarded-For, which is only as trustworthy as the proxy
that wrote it: Next.js passes a header the browser sent through unchanged, so
unless a proxy in front overwrites it, a determined client can dodge per-client
limits. Server-wide limits (all clients together) can't be dodged that way, and
are what actually caps spending.

The counts live in this process: with several server workers, each enforces the
limits on its own share of requests.
"""

from __future__ import annotations

import ipaddress
import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Limit:
    count: int  # requests allowed per window; 0 = no limit
    window_s: float


@dataclass(frozen=True)
class Rule:
    """One limit on one key. `client` is "*" for a server-wide limit."""

    bucket: str
    client: str
    limit: Limit
    message: str | None = None  # shown instead of the generic one, for the user


class RateLimited(Exception):
    """Too many requests. The message is for the user."""

    def __init__(self, message: str, retry_after_s: float, wait: str = ""):
        super().__init__(message + wait)
        self.retry_after_s = retry_after_s


def _describe(window_s: float) -> str:
    return {60: "minute", 3600: "hour", 86400: "day"}.get(int(window_s), f"{window_s:g}s")


class RateLimiter:
    # Clients with no recent requests are dropped once this many are tracked,
    # so a flood of addresses can't grow memory without bound.
    MAX_CLIENTS = 10_000

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._hits: dict[tuple[str, str, float], deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, bucket: str, client: str, limits: list[Limit]) -> None:
        """Count one request, or raise RateLimited (counting nothing) if any limit
        is already used up."""
        self.check_all([Rule(bucket, client, lim) for lim in limits])

    def check_all(self, rules: list[Rule]) -> None:
        """Like check(), for limits on several keys at once (e.g. per client and
        server-wide): either every one counts the request, or none does."""
        now = self._clock()
        with self._lock:
            windows = []
            for rule in rules:
                lim = rule.limit
                if lim.count <= 0:
                    continue
                hits = self._hits.setdefault((rule.bucket, rule.client, lim.window_s), deque())
                while hits and hits[0] <= now - lim.window_s:
                    hits.popleft()
                if len(hits) >= lim.count:
                    retry = max(1, math.ceil(hits[0] + lim.window_s - now))
                    raise RateLimited(
                        rule.message
                        or f"Too many requests: the limit is {lim.count} per "
                        f"{_describe(lim.window_s)}.",
                        retry,
                        f" Try again in {_wait(retry)}.",
                    )
                windows.append(hits)
            for hits in windows:
                hits.append(now)
            if len(self._hits) > self.MAX_CLIENTS:
                self._prune(now)

    def _prune(self, now: float) -> None:
        for key in [k for k, hits in self._hits.items() if not hits or hits[-1] <= now - k[2]]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def _wait(seconds: float) -> str:
    if seconds < 90:
        return f"{int(seconds)} seconds"
    if seconds < 5400:
        return f"{round(seconds / 60)} minutes"
    return f"{round(seconds / 3600)} hours"


def client_ip(peer: str | None, forwarded_for: str | None, trusted: list[str]) -> str:
    """The client's address. X-Forwarded-For is believed only when the request came
    from a trusted proxy (by default this machine or a private network), and then
    only up to the first address that isn't itself a trusted proxy, since anything
    left of that could have been written by the client."""
    peer = _normalize(peer or "unknown")
    if not forwarded_for or not _is_trusted(peer, trusted):
        return peer
    for hop in reversed([_normalize(h.strip()) for h in forwarded_for.split(",") if h.strip()]):
        if not _is_trusted(hop, trusted):
            return hop
    return peer


def _normalize(address: str) -> str:
    """One spelling per client: Node reports IPv4 clients as "::ffff:1.2.3.4"."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return address
    mapped = getattr(ip, "ipv4_mapped", None)
    return str(mapped or ip)


def _is_trusted(address: str, trusted: list[str]) -> bool:
    try:
        ip = ipaddress.ip_address(_normalize(address))
    except ValueError:
        return False
    for net in trusted:
        try:
            if ip in ipaddress.ip_network(net, strict=False):
                return True
        except ValueError:
            continue
    return False
