import json

import httpx
from fastapi.testclient import TestClient

import api.main
from api.main import app, get_registry
from askdb.config import Settings
from askdb.sources import SourceRegistry


def make_client(db_path, generator, seen_providers=None, seen_keys=None):
    registry = SourceRegistry(
        Settings(database_url=f"sqlite:///{db_path}", upload_dir=db_path.parent / "uploads")
    )
    db = registry.sample()

    def fake_generator_for(question, provider=None, context=None, api_key=None):  # no network
        if seen_providers is not None:
            seen_providers.append(provider)
        if seen_keys is not None:
            seen_keys.append(api_key)
        generator.context = context
        return generator

    db.generator_for = fake_generator_for
    app.dependency_overrides[get_registry] = lambda: registry
    return TestClient(app)


def test_ask_returns_rows_chart_and_attempts(db_path, scripted):
    gen = scripted(
        "SELECT countr FROM customer",
        "SELECT country, SUM(total) AS revenue FROM orders o "
        "JOIN customer c ON c.id = o.customer_id GROUP BY country ORDER BY revenue DESC",
    )
    client = make_client(db_path, gen)
    res = client.post("/api/ask", json={"question": "revenue by country"})
    assert res.status_code == 200
    body = res.json()
    assert body["columns"] == ["country", "revenue"]
    assert body["rows"][0] == ["US", 30.0]
    assert body["chart"]["type"] == "bar"
    assert [a["stage"] for a in body["attempts"]] == ["execute", None]
    assert body["provider"] == "free" and body["model"] == "gemini-flash-latest"


def test_ask_can_choose_the_open_model(db_path, scripted):
    seen: list = []
    client = make_client(db_path, scripted("SELECT 1 AS one"), seen)
    res = client.post("/api/ask", json={"question": "one", "provider": "local"})
    assert res.status_code == 200
    assert seen == ["local"]
    assert res.json()["provider"] == "local"
    assert "Arctic-Text2SQL-R1-7B" in res.json()["model"]


def test_unknown_provider_is_rejected(db_path, scripted):
    client = make_client(db_path, scripted("SELECT 1"))
    res = client.post("/api/ask", json={"question": "one", "provider": "gpt"})
    assert res.status_code == 422


def test_health_lists_providers(db_path, scripted):
    body = make_client(db_path, scripted()).get("/api/health").json()
    assert set(body["providers"]) == {"claude", "free", "local"}
    assert set(body["configured"]) == {"claude", "free", "local"}


def test_ask_reports_failed_attempts(db_path, scripted):
    client = make_client(db_path, scripted("DROP TABLE orders", "DROP TABLE orders", "x"))
    res = client.post("/api/ask", json={"question": "delete everything"})
    assert res.status_code == 422
    assert len(res.json()["detail"]["attempts"]) == 3


def test_schema_endpoint(db_path, scripted):
    client = make_client(db_path, scripted())
    assert [t["name"] for t in client.get("/api/schema").json()["tables"]] == [
        "customer",
        "orders",
    ]


def parse_sse(text: str) -> list[dict]:
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


def test_stream_emits_progress_then_result(db_path, scripted):
    gen = scripted("SELECT nme FROM customer", "SELECT name FROM customer ORDER BY id")
    client = make_client(db_path, gen)
    res = client.post("/api/ask/stream", json={"question": "names"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(res.text)
    kinds = [(e["type"], e.get("stage")) for e in events]
    assert kinds == [
        ("stage", "generate"),
        ("generated", None),
        ("stage", "validate"),
        ("stage", "execute"),
        ("attempt_failed", "execute"),
        ("stage", "generate"),
        ("generated", None),
        ("stage", "validate"),
        ("stage", "execute"),
        ("result", None),
    ]
    assert events[4]["will_retry"] is True
    assert events[-1]["data"]["rows"] == [["Ada"], ["Linus"], ["Grace"]]


def test_stream_reports_errors_as_events(db_path, scripted):
    client = make_client(db_path, scripted("DROP TABLE orders", "DROP TABLE x", "DELETE FROM t"))
    events = parse_sse(client.post("/api/ask/stream", json={"question": "x"}).text)
    assert events[-1]["type"] == "error"
    assert events[-1]["status"] == 422
    assert len(events[-1]["detail"]["attempts"]) == 3


def test_follow_up_context_reaches_the_generator(db_path, scripted):
    gen = scripted("SELECT 1 AS one")
    client = make_client(db_path, gen)
    body = {
        "question": "only the first one",
        "context": [{"question": "list customers", "sql": "SELECT name FROM customer"}],
    }
    assert client.post("/api/ask", json=body).status_code == 200
    assert gen.context[0].question == "list customers"
    assert gen.context[0].sql == "SELECT name FROM customer"


def test_run_edited_sql(db_path, scripted):
    client = make_client(db_path, scripted())
    res = client.post("/api/run", json={"sql": "SELECT name FROM customer WHERE id = 2"})
    assert res.status_code == 200
    assert res.json()["rows"] == [["Linus"]]
    assert res.json()["provider"] == "manual"


def test_run_still_blocks_writes(db_path, scripted):
    client = make_client(db_path, scripted())
    res = client.post("/api/run", json={"sql": "DELETE FROM customer"})
    assert res.status_code == 422
    assert res.json()["detail"]["attempts"][0]["stage"] == "validate"
    # and nothing was deleted
    rows = client.post("/api/run", json={"sql": "SELECT COUNT(*) FROM customer"}).json()["rows"]
    assert rows == [[3]]


def test_users_key_header_reaches_the_generator(db_path, scripted):
    keys: list = []
    client = make_client(db_path, scripted("SELECT 1 AS one", "SELECT 1 AS one"), seen_keys=keys)
    headers = {"X-AskDB-Api-Key": "  my-key  "}
    assert client.post("/api/ask", json={"question": "one"}, headers=headers).status_code == 200
    client.post("/api/ask/stream", json={"question": "one"}, headers=headers)
    client.post("/api/ask", json={"question": "one"})
    assert keys == ["my-key", "my-key", None]


def test_key_check(db_path, scripted, monkeypatch):
    client = make_client(db_path, scripted("SELECT 1"))
    check = lambda key: client.post(  # noqa: E731
        "/api/keys/check", json={"provider": "free"}, headers={"X-AskDB-Api-Key": key}
    ).json()
    assert check("")["ok"] is False

    seen = []
    monkeypatch.setattr(api.main, "list_models", lambda url, key, c: seen.append(key) or ["m"])
    assert check("good") == {"ok": True, "message": "Key works."}
    assert seen == ["good"]

    def rejected(url, key, c):
        req = httpx.Request("GET", url)
        raise httpx.HTTPStatusError("bad", request=req, response=httpx.Response(400, request=req))

    monkeypatch.setattr(api.main, "list_models", rejected)
    assert check("bad") == {"ok": False, "message": "That key was rejected."}


def test_root_points_to_the_web_app(db_path, scripted):
    res = make_client(db_path, scripted("SELECT 1")).get("/")
    assert res.status_code == 200 and "localhost:3000" in res.json()["message"]
