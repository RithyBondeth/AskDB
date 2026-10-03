from fastapi.testclient import TestClient

from api.main import app, get_askdb
from askdb.config import Settings
from askdb.pipeline import AskDB


def make_client(db_path, generator, seen_providers=None):
    db = AskDB.from_settings(Settings(database_url=f"sqlite:///{db_path}"))

    def fake_generator_for(question, provider=None):  # no network in tests
        if seen_providers is not None:
            seen_providers.append(provider)
        return generator

    db.generator_for = fake_generator_for
    app.dependency_overrides[get_askdb] = lambda: db
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
    assert body["provider"] == "claude" and body["model"] == "claude-opus-5-5"


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
    assert set(body["providers"]) == {"claude", "local"}


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
