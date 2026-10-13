"""Uploading SQLite files and CSVs, and querying them."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from api.main import app, get_registry
from askdb.config import Settings
from askdb.db import QueryError, run_query
from askdb.importers import UploadError, csvs_to_sqlite, sanitize_identifier
from askdb.sources import SourceRegistry, suggest_questions

SALES_CSV = b"""Order ID,Customer Name,Order Date,Amount
1,Ada,2024-01-05,10.5
2,Linus,2024-02-10,20
3,Ada,2024-02-11,
"""


@pytest.fixture
def registry(db_path, tmp_path):
    return SourceRegistry(
        Settings(
            database_url=f"sqlite:///{db_path}",
            upload_dir=tmp_path / "uploads",
            max_upload_mb=1,
            max_uploads=3,
        )
    )


# Each browser sends its own random id; uploads belong to the id that made them.
ME = "browser-me-0123456789"
OTHER = "browser-other-0123456789"


@pytest.fixture
def client(registry):
    app.dependency_overrides[get_registry] = lambda: registry
    yield TestClient(app, headers={"X-AskDB-Owner": ME})
    app.dependency_overrides.clear()


@pytest.fixture
def other(registry, client):
    """A second browser using the same server."""
    return TestClient(app, headers={"X-AskDB-Owner": OTHER})


def upload(client, *files, name=None):
    data = {"name": name} if name else {}
    return client.post(
        "/api/databases",
        files=[("files", (fname, content)) for fname, content in files],
        data=data,
    )


def test_sanitize_identifier():
    assert sanitize_identifier("Order Date", "x") == "order_date"
    assert sanitize_identifier("customerID", "x") == "customer_id"
    assert sanitize_identifier("2024 sales", "x") == "_2024_sales"
    assert sanitize_identifier("***", "fallback") == "fallback"


def test_csv_becomes_typed_table(tmp_path):
    dest = tmp_path / "out.sqlite"
    assert csvs_to_sqlite([("Sales Data.csv", SALES_CSV)], dest) == ["sales_data"]
    conn = sqlite3.connect(dest)
    cols = {r[1]: r[2] for r in conn.execute("PRAGMA table_info(sales_data)")}
    assert cols == {
        "order_id": "INTEGER",
        "customer_name": "TEXT",
        "order_date": "TEXT",
        "amount": "REAL",
    }
    assert conn.execute("SELECT SUM(amount), COUNT(*) FROM sales_data").fetchone() == (30.5, 3)
    assert conn.execute("SELECT amount FROM sales_data WHERE order_id = 3").fetchone() == (None,)


def test_csv_semicolon_and_type_fallback(tmp_path):
    data = b"name;value\na;1\nb;2\n" + b"".join(b"x;3\n" for _ in range(6000)) + b"c;oops\n"
    dest = tmp_path / "out.sqlite"
    csvs_to_sqlite([("t.csv", data)], dest)
    cols = {r[1]: r[2] for r in sqlite3.connect(dest).execute("PRAGMA table_info(t)")}
    assert cols["value"] == "TEXT"  # a non-number after the sample


def test_csv_needs_rows(tmp_path):
    with pytest.raises(UploadError, match="header row"):
        csvs_to_sqlite([("empty.csv", b"a,b\n")], tmp_path / "x.sqlite")


def test_upload_csvs_then_query(client, registry):
    res = upload(client, ("sales.csv", SALES_CSV), ("people.csv", b"name,city\nAda,London\n"))
    assert res.status_code == 200, res.text
    info = res.json()
    assert info["kind"] == "csv" and info["tables"] == 2 and info["name"] == "2 CSV files"

    listed = client.get("/api/databases").json()
    assert [d["id"] for d in listed["databases"]] == ["sample", info["id"]]

    schema = client.get("/api/schema", params={"database": info["id"]}).json()
    assert sorted(t["name"] for t in schema["tables"]) == ["people", "sales"]
    assert schema["suggestions"]

    res = client.post(
        "/api/run",
        json={
            "database": info["id"],
            "sql": "SELECT p.city, SUM(s.amount) FROM sales s "
            "JOIN people p ON p.name = s.customer_name GROUP BY 1",
        },
    )
    assert res.status_code == 200
    assert res.json()["rows"] == [["London", 10.5]]


def test_ask_uses_the_chosen_database(client, registry, scripted):
    info = upload(client, ("sales.csv", SALES_CSV)).json()
    db = registry.get(info["id"], ME)
    db.generator_for = lambda q, *args, **kwargs: scripted("SELECT COUNT(*) FROM sales")
    res = client.post("/api/ask", json={"question": "how many", "database": info["id"]})
    assert res.status_code == 200
    assert res.json()["rows"] == [[3]]


def test_upload_sqlite_file(client, tmp_path):
    src = tmp_path / "mine.db"
    conn = sqlite3.connect(src)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("CREATE TABLE pets (name TEXT, age INTEGER)")
    conn.execute("INSERT INTO pets VALUES ('Rex', 3)")
    conn.commit()
    conn.close()
    info = upload(client, ("mine.db", src.read_bytes()), name="My pets").json()
    assert info["kind"] == "sqlite" and info["name"] == "My pets"
    res = client.post("/api/run", json={"database": info["id"], "sql": "SELECT * FROM pets"})
    assert res.json()["rows"] == [["Rex", 3]]


def test_uploaded_database_is_read_only(client, registry):
    info = upload(client, ("sales.csv", SALES_CSV)).json()
    blocked = client.post("/api/run", json={"database": info["id"], "sql": "DELETE FROM sales"})
    assert blocked.status_code == 422
    # and even bypassing the validator, the connection refuses to write
    with pytest.raises(QueryError, match="readonly"):
        run_query(registry.get(info["id"], ME).engine, "DELETE FROM sales", 10)


def test_rejects_fake_sqlite(client):
    res = upload(client, ("evil.db", b"not a database at all"))
    assert res.status_code == 400
    assert "isn't a SQLite" in res.json()["detail"]["message"]


def test_rejects_unknown_types_and_mixing(client):
    assert upload(client, ("x.exe", b"MZ")).status_code == 400
    assert upload(client, ("a.csv", SALES_CSV), ("b.db", b"x")).status_code == 400


def test_size_and_count_limits(client):
    big = b"a,b\n" + b"1,2\n" * 300_000  # > 1 MB
    assert upload(client, ("big.csv", big)).status_code == 413
    for i in range(3):
        assert upload(client, (f"t{i}.csv", SALES_CSV)).status_code == 200
    res = upload(client, ("one-more.csv", SALES_CSV))
    assert res.status_code == 400 and "limit" in res.json()["detail"]["message"]


def test_uploads_can_be_turned_off(db_path, tmp_path):
    registry = SourceRegistry(
        Settings(
            database_url=f"sqlite:///{db_path}", upload_dir=tmp_path / "u", allow_uploads=False
        )
    )
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        res = upload(TestClient(app, headers={"X-AskDB-Owner": ME}), ("s.csv", SALES_CSV))
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 400 and "turned off" in res.json()["detail"]["message"]


def test_delete_and_unknown_ids(client):
    info = upload(client, ("sales.csv", SALES_CSV)).json()
    assert client.delete(f"/api/databases/{info['id']}").status_code == 200
    assert client.get("/api/schema", params={"database": info["id"]}).status_code == 404
    assert client.delete("/api/databases/sample").status_code == 400
    assert client.get("/api/schema", params={"database": "../../etc/passwd"}).status_code == 404


def test_uploads_are_private_to_their_browser(client, other):
    info = upload(client, ("sales.csv", SALES_CSV)).json()
    db = info["id"]
    assert [d["id"] for d in other.get("/api/databases").json()["databases"]] == ["sample"]
    # Querying or deleting someone else's upload looks the same as a missing one.
    assert other.get("/api/schema", params={"database": db}).status_code == 404
    assert other.post("/api/run", json={"database": db, "sql": "SELECT 1"}).status_code == 404
    assert other.post("/api/ask", json={"question": "q", "database": db}).status_code == 404
    assert other.delete(f"/api/databases/{db}").status_code == 404
    # ...and the owner still has it.
    assert client.get("/api/schema", params={"database": db}).status_code == 200
    assert "owner" not in client.get("/api/databases").json()["databases"][1]


def test_upload_needs_a_browser_id(client):
    for headers in ({}, {"X-AskDB-Owner": "short"}, {"X-AskDB-Owner": "has spaces in it ok?"}):
        res = TestClient(app, headers=headers).post(
            "/api/databases", files=[("files", ("s.csv", SALES_CSV))]
        )
        assert res.status_code == 400, headers
        assert "id" in res.json()["detail"]["message"]


def test_upload_limit_is_per_browser_with_a_global_cap(client, other, registry):
    for i in range(3):
        assert upload(client, (f"t{i}.csv", SALES_CSV)).status_code == 200
    assert upload(client, ("more.csv", SALES_CSV)).status_code == 400
    assert upload(other, ("theirs.csv", SALES_CSV)).status_code == 200  # own quota

    registry.settings.max_total_uploads = 4
    res = upload(other, ("full.csv", SALES_CSV))
    assert res.status_code == 400 and "full" in res.json()["detail"]["message"]


def test_owner_id_is_not_stored(client, registry):
    upload(client, ("sales.csv", SALES_CSV))
    meta = next(registry.dir.glob("*.json")).read_text()
    assert ME not in meta and '"owner": "' in meta


def test_ownerless_uploads_are_shared(registry, client, other):
    """Uploads from before scoping (or from the CLI) stay visible to everyone."""
    info = registry.add([("sales.csv", SALES_CSV)])
    for c in (client, other):
        assert c.get("/api/schema", params={"database": info.id}).status_code == 200


def test_uploads_survive_restart(registry, db_path):
    info = registry.add([("sales.csv", SALES_CSV)])
    fresh = SourceRegistry(registry.settings)
    assert info.id in [s.id for s in fresh.list()]
    assert fresh.get(info.id).schema.tables[0].name == "sales"


def test_uploaded_db_prompt_has_its_own_examples_and_real_date(registry):
    import datetime as dt

    info = registry.add([("sales.csv", SALES_CSV)])
    db = registry.get(info.id)
    gen = db.generator_for("total amount", provider="claude", api_key="k")
    assert "Artist" not in gen.system_prompt
    assert "Examples:" in gen.system_prompt
    assert "FROM sales" in gen.system_prompt  # examples written for this upload
    assert dt.date.today().isoformat() in gen.system_prompt
    assert "CREATE TABLE sales" in gen.system_prompt


def test_suggestions_from_schema(registry):
    info = registry.add([("sales.csv", SALES_CSV)])
    qs = suggest_questions(registry.get(info.id).schema)
    assert "Top 10 customer name by total amount in sales" in qs
    assert "Total amount per month in sales" in qs
    assert "How many rows are in sales?" in qs


def test_suggestions_prefer_money_and_name_columns(registry):
    orders = (
        b"Order ID,Order Date,Customer Name,Product,Quantity,Revenue\n"
        b"1,2024-01-01,Ada,Laptop,2,2400\n2,2024-02-01,Linus,Dock,1,220\n"
    )
    info = registry.add([("orders.csv", orders)])
    qs = suggest_questions(registry.get(info.id).schema)
    assert qs[:3] == [
        "Top 10 customer name by total revenue in orders",
        "Total revenue per month in orders",
        "Total revenue by product in orders",
    ]


# ------------------------------------------------------------------ expiry and memory


def _age(registry, source_id, days):
    import os
    import time

    meta = registry.dir / f"{source_id}.json"
    old = time.time() - days * 86400
    os.utime(meta, (old, old))


def _expiring(db_path, tmp_path, removed=None):
    return SourceRegistry(
        Settings(database_url=f"sqlite:///{db_path}", upload_dir=tmp_path / "u", upload_ttl_days=7),
        on_remove=removed.append if removed is not None else None,
    )


def test_unused_uploads_expire_with_their_saved_answers(db_path, tmp_path):
    removed: list[str] = []
    registry = _expiring(db_path, tmp_path, removed)
    stale = registry.add([("old.csv", SALES_CSV)])
    fresh = registry.add([("new.csv", SALES_CSV)])
    _age(registry, stale.id, 8)
    _age(registry, fresh.id, 6)
    assert registry.expire() == [stale.id]
    assert removed == [stale.id]  # the API drops its saved answers here
    assert not (registry.dir / f"{stale.id}.sqlite").exists()
    assert [s.id for s in registry.list()] == ["sample", fresh.id]


def test_unused_connections_expire_too(db_path, tmp_path):
    # A saved connection string holds a password; an abandoned one shouldn't linger.
    import json
    from dataclasses import asdict

    from askdb.sources import SourceInfo

    registry = _expiring(db_path, tmp_path)
    registry.dir.mkdir(parents=True)
    info = SourceInfo(
        id="ab" * 16, name="shop", kind="postgres", tables=3, size_bytes=0,
        created_at="2026-01-01T00:00:00+00:00", url="postgresql://u:secret@db.example.com/shop",
    )  # fmt: skip
    (registry.dir / f"{info.id}.json").write_text(json.dumps(asdict(info)))
    _age(registry, info.id, 30)
    assert registry.expire() == [info.id]
    assert not (registry.dir / f"{info.id}.json").exists()


def test_using_an_upload_keeps_it(db_path, tmp_path):
    registry = _expiring(db_path, tmp_path)
    info = registry.add([("sales.csv", SALES_CSV)])
    _age(registry, info.id, 8)
    registry.get(info.id)  # a question was asked of it
    assert registry.expire() == []


def test_expiry_frees_room_for_new_uploads(registry):
    registry.settings.upload_ttl_days = 7
    old = [registry.add([(f"{i}.csv", SALES_CSV)], owner=ME) for i in range(3)]
    with pytest.raises(UploadError, match="limit reached"):
        registry.add([("one-more.csv", SALES_CSV)], owner=ME)
    _age(registry, old[0].id, 30)
    assert registry.add([("one-more.csv", SALES_CSV)], owner=ME)


def test_zero_ttl_keeps_uploads_forever(registry):
    registry.settings.upload_ttl_days = 0
    info = registry.add([("sales.csv", SALES_CSV)])
    _age(registry, info.id, 3650)
    assert registry.expire() == []


def test_least_recently_used_databases_are_closed(registry):
    registry.settings.max_open_databases = 2
    a, b, c = (registry.add([(f"{n}.csv", SALES_CSV)]) for n in "abc")
    registry.get(a.id)
    registry.get(b.id)
    registry.get(a.id)  # a is now the most recently used
    registry.get(c.id)  # opening c closes b
    assert set(registry._cache) - {"sample"} == {a.id, c.id}
    # A closed database reopens on its next use.
    assert registry.get(b.id).run("SELECT COUNT(*) FROM b").result.rows == [[3]]
    assert b.id in registry._cache and a.id not in registry._cache
