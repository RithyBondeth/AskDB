"""Per-client request limits."""

import pytest
from fastapi.testclient import TestClient

from api.main import app, get_registry
from askdb.config import Settings
from askdb.ratelimit import Limit, RateLimited, RateLimiter, client_ip
from askdb.sources import SourceRegistry


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_sliding_window_blocks_then_recovers():
    clock = Clock()
    limiter = RateLimiter(clock)
    for _ in range(3):
        limiter.check("ask", "1.2.3.4", [Limit(3, 60)])
    with pytest.raises(RateLimited, match="3 per minute") as exc:
        limiter.check("ask", "1.2.3.4", [Limit(3, 60)])
    assert exc.value.retry_after_s == 60
    limiter.check("ask", "5.6.7.8", [Limit(3, 60)])  # other clients are unaffected
    clock.now += 60
    limiter.check("ask", "1.2.3.4", [Limit(3, 60)])


def test_a_blocked_request_is_not_counted():
    clock = Clock()
    limiter = RateLimiter(clock)
    limits = [Limit(10, 60), Limit(2, 86400)]
    limiter.check("ask", "c", limits)
    limiter.check("ask", "c", limits)
    with pytest.raises(RateLimited, match="per day"):
        limiter.check("ask", "c", limits)
    # The refused request didn't use up the per-minute window either.
    for _ in range(8):
        limiter.check("ask", "c", [Limit(10, 60)])


def test_zero_means_no_limit():
    limiter = RateLimiter()
    for _ in range(100):
        limiter.check("ask", "c", [Limit(0, 60)])


def test_idle_clients_are_forgotten():
    clock = Clock()
    limiter = RateLimiter(clock)
    limiter.MAX_CLIENTS = 5
    for i in range(5):
        limiter.check("ask", f"c{i}", [Limit(1, 60)])
    clock.now += 61
    limiter.check("ask", "new", [Limit(1, 60)])
    assert len(limiter._hits) == 1


TRUSTED = ["127.0.0.1", "::1", "10.0.0.0/8"]


@pytest.mark.parametrize(
    ("peer", "xff", "expected"),
    [
        ("127.0.0.1", "203.0.113.7", "203.0.113.7"),  # via the Next.js proxy
        ("127.0.0.1", "203.0.113.7, 10.0.0.2", "203.0.113.7"),  # and a load balancer
        ("127.0.0.1", "6.6.6.6, 203.0.113.7", "203.0.113.7"),  # forged left entry ignored
        ("198.51.100.1", "203.0.113.7", "198.51.100.1"),  # untrusted peer: header ignored
        ("127.0.0.1", None, "127.0.0.1"),
        ("127.0.0.1", "garbage", "garbage"),
        # Node spells IPv4 clients as IPv4-mapped IPv6; both spellings are one client.
        ("::ffff:127.0.0.1", "::ffff:203.0.113.7", "203.0.113.7"),
        ("127.0.0.1", "::ffff:127.0.0.1", "127.0.0.1"),  # a local visitor
    ],
)
def test_client_ip(peer, xff, expected):
    assert client_ip(peer, xff, TRUSTED) == expected


# ------------------------------------------------------------------ through the API


@pytest.fixture
def api(db_path, scripted):
    registry = SourceRegistry(
        Settings(
            database_url=f"sqlite:///{db_path}",
            upload_dir=db_path.parent / "uploads",
            ask_per_minute=5,
            ask_per_day=2,
            server_key_asks_per_day=3,
            queries_per_minute=2,
            summaries="simple",  # no second model call per answer
        )
    )
    db = registry.sample()
    db.generator_for = lambda *a, **k: scripted(*["SELECT 1"] * 10)
    app.dependency_overrides[get_registry] = lambda: registry
    yield TestClient(app, client=("127.0.0.1", 50000))
    app.dependency_overrides.clear()


def test_daily_limit_applies_only_to_the_servers_key(api):
    body = {"question": "q", "provider": "free"}
    assert api.post("/api/ask", json=body).status_code == 200
    assert api.post("/api/ask", json=body).status_code == 200
    res = api.post("/api/ask", json=body)
    assert res.status_code == 429
    assert "per day" in res.json()["detail"]["message"]
    assert int(res.headers["Retry-After"]) > 0
    # With their own key, the visitor pays: only the per-minute limit applies.
    own = {"X-AskDB-Api-Key": "mine"}
    assert api.post("/api/ask", json=body, headers=own).status_code == 200


def test_limits_are_per_client_behind_the_proxy(api):
    sql = {"sql": "SELECT 1"}
    a, b = {"X-Forwarded-For": "203.0.113.1"}, {"X-Forwarded-For": "203.0.113.2"}
    assert api.post("/api/run", json=sql, headers=a).status_code == 200
    assert api.post("/api/run", json=sql, headers=a).status_code == 200
    assert api.post("/api/run", json=sql, headers=a).status_code == 429
    assert api.post("/api/run", json=sql, headers=b).status_code == 200


def test_stream_is_limited_before_it_starts(api):
    body = {"question": "q", "provider": "free"}
    for _ in range(2):
        assert api.post("/api/ask/stream", json=body).status_code == 200
    res = api.post("/api/ask/stream", json=body)
    assert res.status_code == 429
    assert res.headers["content-type"].startswith("application/json")


def test_server_wide_budget_cant_be_dodged_by_faking_ips(api):
    # Next.js passes a browser's own X-Forwarded-For through unchanged, so a client
    # can pose as many addresses and get fresh per-client limits each time...
    body = {"question": "q", "provider": "free"}
    for i in range(3):
        fake = {"X-Forwarded-For": f"198.51.100.{i}"}
        assert api.post("/api/ask", json=body, headers=fake).status_code == 200
    # ...but the server key's daily budget counts everyone together.
    res = api.post("/api/ask", json=body, headers={"X-Forwarded-For": "198.51.100.99"})
    assert res.status_code == 429
    assert "own API key" in res.json()["detail"]["message"]
    # Visitors with their own key still get answers.
    own = {"X-AskDB-Api-Key": "mine", "X-Forwarded-For": "198.51.100.99"}
    assert api.post("/api/ask", json=body, headers=own).status_code == 200


def test_rules_count_together_or_not_at_all():
    from askdb.ratelimit import Rule

    limiter = RateLimiter(Clock())
    server_wide = Rule("ask", "*", Limit(1, 60), "Budget used.")
    limiter.check_all([Rule("ask", "a", Limit(5, 60)), server_wide])
    with pytest.raises(RateLimited, match="Budget used"):
        limiter.check_all([Rule("ask", "b", Limit(5, 60)), server_wide])
    # b's refused request wasn't counted against b.
    for _ in range(5):
        limiter.check("ask", "b", [Limit(5, 60)])
