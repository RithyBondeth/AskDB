from fastapi.testclient import TestClient

from api.main import app, get_askdb
from askdb.config import Settings
from askdb.pipeline import AskDB


def make_client(db_path, generator):
    db = AskDB.from_settings(Settings(database_url=f"sqlite:///{db_path}"))
    db.generator_for = lambda question: generator  # no network in tests
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
