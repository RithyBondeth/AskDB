"""Charts, summaries, schema linking, saved answers, feedback, paging, export, and
live connections."""

import json
import os
import re

import pytest
from fastapi.testclient import TestClient

from api.main import app, get_registry
from askdb.config import Settings
from askdb.db import QueryError, make_engine, run_query
from askdb.generate import Generation, build_summary_prompt, clean_summary
from askdb.importers import UploadError
from askdb.linking import SchemaIndex, split_identifier, stem
from askdb.pipeline import AskDB, similar_examples
from askdb.present import describe_result, pick_chart
from askdb.schema import Column, ForeignKey, Schema, Table
from askdb.sources import SourceRegistry, display_url, parse_connection
from askdb.validate import validate_sql

ME = "browser-one-0123456789"
YOU = "browser-two-0123456789"


# ---------------------------------------------------------------- charts


def test_share_question_gets_a_pie():
    rows = [["Rock", 50], ["Jazz", 30], ["Pop", 20]]
    spec = pick_chart(["genre", "tracks"], rows, "What share of tracks is each genre?")
    assert spec.type == "pie" and spec.x == "genre" and spec.y == ["tracks"]
    # The same result without a share question is a ranking: bars.
    assert pick_chart(["genre", "tracks"], rows, "tracks per genre").type == "bar"


def test_pie_needs_few_non_negative_slices():
    many = [[f"g{i}", i + 1] for i in range(12)]
    assert pick_chart(["genre", "n"], many, "breakdown by genre").type == "bar"
    negative = [["a", 5], ["b", -2]]
    assert pick_chart(["k", "v"], negative, "share by k").type == "bar"


def test_long_format_gets_a_stacked_bar():
    rows = [["US", "Rock", 10], ["US", "Jazz", 4], ["UK", "Rock", 7], ["UK", "Jazz", 2]]
    spec = pick_chart(["country", "genre", "revenue"], rows)
    assert (spec.type, spec.x, spec.group, spec.y) == ("bar", "country", "genre", ["revenue"])


def test_long_format_over_time_gets_one_line_per_group():
    rows = [["2024-01", "Rock", 10], ["2024-01", "Jazz", 4], ["2024-02", "Rock", 7]]
    spec = pick_chart(["month", "genre", "revenue"], rows)
    assert (spec.type, spec.x, spec.group) == ("line", "month", "genre")


def test_two_measures_get_a_scatter():
    rows = [[3.5, 10.0], [1.2, 4.0], [8.0, 2.5]]
    spec = pick_chart(["price", "sales"], rows)
    assert (spec.type, spec.x, spec.y) == ("scatter", "price", ["sales"])


def test_many_labelled_points_get_a_scatter_with_labels():
    rows = [[f"track {i}", i * 1.5, i * 2] for i in range(40)]
    spec = pick_chart(["track", "length", "plays"], rows)
    assert (spec.type, spec.x, spec.y, spec.label) == ("scatter", "length", ["plays"], "track")


def test_year_column_is_still_a_bar_label():
    rows = [[2011, 100.0], [2012, 120.0], [2013, 90.0]]
    assert pick_chart(["year", "revenue"], rows).type == "bar"


# ---------------------------------------------------------------- summaries


def test_describe_result_sentences():
    assert describe_result(["n"], [[275]]) == "The answer is 275 (n)."
    assert describe_result(["a"], []) == "No rows matched."
    ranked = describe_result(["name", "album_count"], [["Iron Maiden", 21], ["AC/DC", 2]])
    assert ranked.startswith("Iron Maiden has the highest album count (21)")
    trend = describe_result(["month", "revenue"], [["2013-01", 10.0], ["2013-02", 30.5]])
    assert "from 10 (2013-01) to 30.50 (2013-02)" in trend


def test_summary_prompt_shows_a_capped_table():
    rows = [[i, f"name {i}"] for i in range(50)]
    prompt = build_summary_prompt("q?", ["id", "name"], rows, truncated=True)
    assert "id | name" in prompt and "name 29" in prompt and "name 30" not in prompt
    assert "there are more" in prompt
    assert clean_summary('  "**Iron Maiden** has 21."  ') == "Iron Maiden has 21."


class SummarizingGenerator:
    def __init__(self, sql, summary=None, fail=False):
        self.sql, self.summary, self.fail = sql, summary, fail

    def generate(self, question, repairs=None):
        return Generation(self.sql, "")

    def summarize(self, question, columns, rows, truncated):
        if self.fail:
            raise RuntimeError("model down")
        return self.summary


def test_model_summary_and_its_fallback(db_path):
    db = AskDB.from_settings(Settings(database_url=f"sqlite:///{db_path}", _env_file=None))
    ans = db.ask(
        "how many customers", generator=SummarizingGenerator("SELECT COUNT(*) FROM customer")
    )
    db.generator_for = lambda *a, **k: SummarizingGenerator("", "There are 3 customers.")
    assert db.summarize(ans, "free") == "There are 3 customers."
    db.generator_for = lambda *a, **k: SummarizingGenerator("", fail=True)
    assert db.summarize(ans, "free") == "The answer is 3 (count(*))."
    # The open model only writes SQL: always the template.
    assert db.summarize(ans, "local") == "The answer is 3 (count(*))."
    db.settings.summaries = "off"
    assert db.summarize(ans, "free") is None


# ---------------------------------------------------------------- linking


def big_schema() -> Schema:
    def t(name, cols, fks=()):
        return Table(
            name,
            [Column(c, "INTEGER" if c.endswith("id") else "TEXT") for c in cols],
            [ForeignKey([c], ref, ["id"]) for c, ref in fks],
        )

    tables = [
        t("customer", ["id", "name", "country"]),
        t("invoice", ["id", "customer_id", "total", "invoiced_at"], [("customer_id", "customer")]),
        t("playlist", ["id", "name"]),
        t("track", ["id", "name", "genre_id"], [("genre_id", "genre")]),
        t("genre", ["id", "name"]),
        t(
            "playlist_track",
            ["playlist_id", "track_id"],
            [("playlist_id", "playlist"), ("track_id", "track")],
        ),
    ]
    tables += [t(f"audit_log_{i}", ["id", "event", "payload"]) for i in range(20)]
    return Schema("sqlite", tables)


def test_identifier_splitting_and_stemming():
    assert split_identifier("InvoiceLine") == ["invoice", "line"]
    assert split_identifier("HTTPStatus_code") == ["http", "status", "code"]
    assert [stem(w) for w in ("customers", "categories", "boxes", "status")] == [
        "customer",
        "category",
        "box",
        "status",
    ]


def test_bm25_picks_tables_and_their_references():
    picked = {t.name for t in SchemaIndex(big_schema()).link("total invoices per customer country")}
    assert {"invoice", "customer"} <= picked
    assert not any(n.startswith("audit_log") for n in picked)


def test_junction_tables_are_pulled_in():
    picked = {t.name for t in SchemaIndex(big_schema()).link("tracks on each playlist")}
    assert {"playlist", "track", "playlist_track"} <= picked


class FakeEmbedder:
    """Vectors by keyword, so "spend" can find `invoice` without sharing a word."""

    def __init__(self, fail=False):
        self.calls, self.fail = 0, fail

    def embed(self, texts):
        self.calls += 1
        if self.fail:
            raise RuntimeError("quota")
        words = ("invoice", "spend", "customer", "audit")
        return [
            [1.0 if ("invoice" in t.lower() or "spend" in t.lower()) else 0.0]
            + [float(w in t.lower()) for w in words]
            for t in texts
        ]


def test_embeddings_find_tables_keywords_miss():
    question = "how much did people spend"  # no table or column shares a word
    # Keywords alone fall back to the most connected tables.
    assert SchemaIndex(big_schema()).link(question)[0].name != "invoice"
    index = SchemaIndex(big_schema(), FakeEmbedder())
    assert index.link(question)[0].name == "invoice"
    index.link("again")  # table vectors are computed once
    assert index.embedder.calls == 3


def test_embeddings_work_right_after_boot(monkeypatch):
    # time.monotonic() counts from boot: a fresh container is at a few seconds.
    monkeypatch.setattr("askdb.linking.time.monotonic", lambda: 5.0)
    index = SchemaIndex(big_schema(), FakeEmbedder())
    assert index.link("how much did people spend")[0].name == "invoice"


def test_failing_embeddings_fall_back_to_keywords():
    index = SchemaIndex(big_schema(), FakeEmbedder(fail=True))
    assert "customer" in {t.name for t in index.link("customers by country")}
    index.link("customers by country")
    assert index.embedder.calls == 1  # not retried straight away


def test_similar_examples_prefers_shared_words():
    examples = [("Top genres by tracks", "A"), ("Revenue by country", "B"), ("Unrelated", "C")]
    assert similar_examples("revenue per country in 2013", examples, 2) == [
        ("Revenue by country", "B")
    ]
    assert similar_examples("x", examples, 0) == []


# ---------------------------------------------------------------- validation & paging


def test_postgres_dialect_name_validates():
    assert validate_sql("SELECT 1", "postgresql") == "SELECT 1"


def test_run_query_offset(engine):
    page = run_query(engine, "SELECT id FROM customer ORDER BY id", row_limit=1, offset=1)
    assert page.rows == [[2]] and page.truncated
    assert run_query(engine, "SELECT id FROM customer", row_limit=5, offset=10).rows == []


# ---------------------------------------------------------------- API


@pytest.fixture
def registry(db_path):
    return SourceRegistry(
        Settings(
            database_url=f"sqlite:///{db_path}",
            upload_dir=db_path.parent / "uploads",
            summaries="simple",
            _env_file=None,
        )
    )


@pytest.fixture
def client(registry, scripted):
    db = registry.sample()
    db.seen_examples = []

    def fake_generator_for(question, provider=None, context=None, api_key=None, model=None,
                           extra_examples=None):  # fmt: skip
        db.seen_examples.append(extra_examples)
        return scripted(db.next_sql)

    db.next_sql = "SELECT name, country FROM customer ORDER BY id"
    db.generator_for = fake_generator_for
    app.dependency_overrides[get_registry] = lambda: registry
    yield TestClient(app)
    app.dependency_overrides.pop(get_registry, None)


def headers(owner=ME):
    return {"X-AskDB-Owner": owner}


def test_answers_are_saved_with_a_summary(client):
    res = client.post("/api/ask", json={"question": "customers"}, headers=headers()).json()
    assert res["id"] and res["summary"] == "3 rows."
    listed = client.get("/api/history?database=sample", headers=headers()).json()["answers"]
    assert [a["question"] for a in listed] == ["customers"]
    saved = client.get(f"/api/history/{res['id']}", headers=headers()).json()
    assert saved["response"]["rows"] == res["rows"]
    # Another browser can't see it, nor list it.
    assert client.get(f"/api/history/{res['id']}", headers=headers(YOU)).status_code == 404
    assert client.get("/api/history", headers=headers(YOU)).json()["answers"] == []


def test_streamed_answers_are_saved_with_their_summary(client, store):
    text = client.post("/api/ask/stream", json={"question": "names"}, headers=headers()).text
    events = [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]
    [result] = [e for e in events if e["type"] == "result"]
    assert events[-1] == {"type": "summary", "text": "3 rows."}
    saved = store.get_answer(ME, result["data"]["id"])
    assert saved["response"]["summary"] == "3 rows."


def test_no_owner_means_nothing_saved(client):
    res = client.post("/api/ask", json={"question": "customers"}).json()
    assert res["id"] is None and res["rows"]


def test_sharing_a_saved_answer(client):
    answer_id = client.post("/api/ask", json={"question": "c"}, headers=headers()).json()["id"]
    url = f"/api/history/{answer_id}"
    assert client.post(f"{url}/share", json={}, headers=headers(YOU)).status_code == 404
    assert client.post(f"{url}/share", json={}, headers=headers()).json()["shared"] is True
    shared = client.get(url).json()  # anyone with the link, even without an owner id
    assert shared["response"]["question"] == "c" and shared["shared"]
    client.post(f"{url}/share", json={"shared": False}, headers=headers())
    assert client.get(url).status_code == 404


def test_deleting_history(client):
    for q in ("a", "b"):
        client.post("/api/ask", json={"question": q}, headers=headers())
    [first, second] = client.get("/api/history", headers=headers()).json()["answers"]
    assert client.delete(f"/api/history/{first['id']}", headers=headers(YOU)).status_code == 404
    assert client.delete(f"/api/history/{first['id']}", headers=headers()).json()["deleted"] == 1
    assert client.delete("/api/history?database=sample", headers=headers()).json()["deleted"] == 1


def test_feedback_is_reused_as_examples(client, registry):
    db = registry.sample()
    ans = client.post("/api/ask", json={"question": "Customers by country"}, headers=headers())
    body = {
        "answer_id": ans.json()["id"],
        "question": "Customers by country",
        "sql": "SELECT country FROM customer",
        "corrected_sql": "SELECT country, COUNT(*) FROM customer GROUP BY country",
        "rating": -1,
    }
    assert client.post("/api/feedback", json=body, headers=headers()).status_code == 200
    rated = client.get("/api/history", headers=headers()).json()["answers"][0]
    assert rated["rating"] == -1

    client.post("/api/ask", json={"question": "customer count by country"}, headers=headers())
    assert db.seen_examples[-1] == [
        ("Customers by country", "SELECT country, COUNT(*) FROM customer GROUP BY country")
    ]
    # Another browser's prompts don't get this browser's feedback.
    client.post("/api/ask", json={"question": "customer count by country"}, headers=headers(YOU))
    assert db.seen_examples[-1] == []


def test_corrected_sql_must_be_read_only(client):
    body = {
        "question": "q",
        "sql": "SELECT 1",
        "corrected_sql": "DROP TABLE customer",
        "rating": -1,
    }
    res = client.post("/api/feedback", json=body, headers=headers())
    assert res.status_code == 400 and "isn't valid" in res.json()["detail"]["message"]
    assert client.post("/api/feedback", json=body | {"corrected_sql": None}).status_code == 400


def test_feedback_examples_dedupe_and_skip_unverified(store):
    store.add_feedback(ME, "sample", "Q one", "SELECT 1", 1)
    store.add_feedback(ME, "sample", "q ONE", "SELECT 2", 1)  # same question: the newest counts
    store.add_feedback(ME, "sample", "Bad", "SELECT 3", -1)  # 👎 without a fix: not an example
    examples = store.examples("sample", ME)
    assert [(e.question, e.sql) for e in examples] == [("q ONE", "SELECT 2")]  # newest first


def test_saved_answers_are_capped_per_owner(tmp_path):
    from askdb.store import Store

    s = Store(tmp_path / "cap.sqlite", max_answers_per_owner=2)
    resp = {"question": "q", "sql": "SELECT 1", "provider": "free", "model": "m"}
    ids = [s.save_answer(ME, "sample", resp | {"question": f"q{i}"}) for i in range(3)]
    assert [a.id for a in s.list_answers(ME)] == [ids[2], ids[1]]


def test_more_rows_pages_through_the_result(client):
    body = {"sql": "SELECT id FROM customer ORDER BY id", "offset": 1, "limit": 1}
    page = client.post("/api/rows", json=body).json()
    assert page == {"columns": ["id"], "rows": [[2]], "truncated": True}
    blocked = client.post("/api/rows", json=body | {"sql": "DELETE FROM customer"})
    assert blocked.status_code == 422


def test_export_streams_every_row_as_csv(client, registry):
    registry.settings.export_row_limit = 2
    res = client.post("/api/export", json={"sql": "SELECT id, name FROM customer ORDER BY id"})
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
    assert res.text.splitlines() == ["id,name", "1,Ada", "2,Linus"]
    assert client.post("/api/export", json={"sql": "DROP TABLE customer"}).status_code == 422


# ---------------------------------------------------------------- connections


def test_connection_strings_are_checked():
    parsed, kind = parse_connection("postgres://app:s3cret@db.example.com:5433/shop")
    assert kind == "postgres" and display_url(parsed) == "app@db.example.com:5433/shop"
    assert parse_connection("mysql://u:p@h/db")[1] == "mysql"
    for bad, why in [
        ("sqlite:///etc/passwd", "Only PostgreSQL and MySQL"),
        ("not a url", "isn't a valid"),
        ("postgresql:///shop", "needs a host"),
        ("postgresql://u@host", "needs a database"),
    ]:
        with pytest.raises(UploadError, match=why):
            parse_connection(bad)


def test_private_hosts_can_be_blocked(registry):
    registry.settings.allow_private_hosts = False
    for host in ("localhost", "127.0.0.1", "10.0.0.5", "169.254.169.254"):
        with pytest.raises(UploadError, match="private or local"):
            registry.connect(f"postgresql://u:p@{host}:5432/db", owner=ME)


def test_failed_connections_hide_the_password(registry):
    with pytest.raises(UploadError) as err:
        # Nothing listens on port 1, so this fails fast without network access.
        registry.connect("postgresql://u:hunter2secret@127.0.0.1:1/db", owner=ME)
    assert "Couldn't connect" in str(err.value) and "hunter2secret" not in str(err.value)


def test_connect_endpoint_needs_an_owner_and_reports_errors(client):
    res = client.post("/api/databases/connect", json={"url": "sqlite:///x.db"})
    assert res.status_code == 400 and "id" in res.json()["detail"]["message"]
    res = client.post("/api/databases/connect", json={"url": "sqlite:///x.db"}, headers=headers())
    assert res.status_code == 400 and "PostgreSQL" in res.json()["detail"]["message"]


LIVE_DATABASES = [
    # kind, env var with a disposable database's URL, a query that runs too long
    ("postgres", "ASKDB_TEST_POSTGRES_URL", "SELECT pg_sleep(5)"),
    # Not SLEEP(): MySQL cuts it short at the limit but returns 1 instead of an error.
    (
        "mysql",
        "ASKDB_TEST_MYSQL_URL",
        "SELECT COUNT(*) FROM information_schema.columns a, information_schema.columns b, "
        "information_schema.columns c",
    ),
]


@pytest.mark.parametrize("kind,env,slow_sql", LIVE_DATABASES, ids=[d[0] for d in LIVE_DATABASES])
def test_live_database_connection(client, registry, kind, env, slow_sql):
    """Against a real server (CI runs Postgres and MySQL services). Use a user that
    *can* write, to show the session itself is read-only."""
    url = os.environ.get(env)
    if not url:
        pytest.skip(f"set {env} to a disposable {kind} database to run")
    registry.settings.statement_timeout_s = 1
    res = client.post("/api/databases/connect", json={"url": url, "name": kind}, headers=headers())
    assert res.status_code == 200, res.text
    info = res.json()
    assert info["kind"] == kind and "url" not in info
    assert ":" not in info["detail"].split("@")[0]  # no password in the display form
    listed = client.get("/api/databases", headers=headers()).json()["databases"]
    assert info["id"] in [d["id"] for d in listed]
    theirs = client.get("/api/databases", headers=headers(YOU)).json()["databases"]
    assert info["id"] not in [d["id"] for d in theirs]

    db = registry.get(info["id"], ME)
    table = db.schema.tables[0].name
    ok = client.post(
        "/api/run",
        json={"sql": f"SELECT * FROM {table}", "database": info["id"]},
        headers=headers(),
    )
    assert ok.status_code == 200, ok.text
    # Read-only and time-limited even for statements that slip past the validator.
    with pytest.raises(QueryError, match=re.compile("read.only", re.I)):
        run_query(db.engine, f"DELETE FROM {table}", 10)
    with pytest.raises(QueryError, match="timed out"):
        run_query(db.engine, slow_sql, 10)
    assert client.delete(f"/api/databases/{info['id']}", headers=headers()).status_code == 200


def test_unsupported_databases_are_refused():
    for url in ("mssql+pyodbc://u:p@host/db", "oracle://u:p@host/db"):
        with pytest.raises(ValueError, match="supports SQLite, PostgreSQL and MySQL"):
            make_engine(url, 5)
