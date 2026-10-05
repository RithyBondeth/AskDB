"""Spider/BIRD conversion and the eval's per-dataset bookkeeping."""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))

import benchmarks  # noqa: E402
import compare  # noqa: E402
from run_eval import accuracy_by  # noqa: E402

from askdb.scores import load_scores  # noqa: E402


def make_db(path: Path, rows: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE singer (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    conn.executemany(
        "INSERT INTO singer VALUES (?, ?, ?)", [(i, f"s{i}", 20 + i) for i in range(rows)]
    )
    conn.commit()
    conn.close()


def spider_dir(tmp_path: Path) -> Path:
    root = tmp_path / "spider"
    for db in ("concert", "pets", "cars"):
        make_db(root / "database" / db / f"{db}.sqlite", 5)
    items = [
        {"db_id": db, "question": f"q{i} on {db}", "query": "SELECT name FROM singer ORDER BY age"}
        for db in ("concert", "pets", "cars")
        for i in range(4)
    ]
    items += [
        {"db_id": "concert", "question": "broken", "query": "SELECT nope FROM singer"},
        {"db_id": "concert", "question": "writes", "query": "DELETE FROM singer"},
        {"db_id": "gone", "question": "no db", "query": "SELECT 1"},
    ]
    (root / "dev.json").write_text(json.dumps(items))
    return root


def test_spider_subset_is_spread_checked_and_reproducible(tmp_path):
    root = spider_dir(tmp_path)
    rows, skipped = benchmarks.prepare("spider", root, limit=6, seed=1)
    assert len(rows) == 6
    assert sorted(r["db_id"] for r in rows) == [
        "cars",
        "cars",
        "concert",
        "concert",
        "pets",
        "pets",
    ]
    assert all(r["ordered"] and Path(r["database"]).exists() for r in rows)
    assert skipped == {
        "gold SQL fails or times out": 1,
        "gold SQL refused by the read-only check": 1,
        "missing database": 1,
    }
    again, _ = benchmarks.prepare("spider", root, limit=6, seed=1)
    assert again == rows
    other, _ = benchmarks.prepare("spider", root, limit=6, seed=2)
    assert [r["question"] for r in other] != [r["question"] for r in rows]


def test_bird_hints_and_difficulty(tmp_path):
    root = tmp_path / "bird"
    make_db(root / "dev_databases" / "club" / "club.sqlite", 3)
    items = [
        {
            "db_id": "club",
            "question": "Oldest singer?",
            "evidence": "oldest refers to MAX(age)",
            "SQL": "SELECT name FROM singer WHERE age = (SELECT MAX(age) FROM singer)",
            "difficulty": level,
        }
        for level in ("simple", "moderate", "challenging")
    ]
    (root / "dev.json").write_text(json.dumps(items))
    rows, _ = benchmarks.prepare("bird", root, limit=10)
    assert {r["difficulty"] for r in rows} == {"simple", "moderate", "challenging"}
    assert rows[0]["question"] == "Oldest singer?\nHint: oldest refers to MAX(age)"
    assert not rows[0]["ordered"]


def test_main_writes_jsonl(tmp_path, capsys):
    out = tmp_path / "out.jsonl"
    assert (
        benchmarks.main(
            ["spider", "--source", str(spider_dir(tmp_path)), "--limit", "3", "--out", str(out)]
        )
        == 0
    )
    assert len(out.read_text().splitlines()) == 3
    assert "Wrote 3 questions from 3 databases" in capsys.readouterr().out
    assert benchmarks.main(["spider", "--source", str(tmp_path / "nowhere")]) == 1


def test_accuracy_by_difficulty():
    results = [
        {"match": True, "difficulty": "simple"},
        {"match": False, "difficulty": "simple"},
        {"match": True, "difficulty": "challenging"},
        {"match": True},
    ]
    assert accuracy_by(results, "difficulty") == {"simple": (1, 2), "challenging": (1, 1)}


def run_file(path: Path, dataset: str | None, model: str, accuracy: float = 0.5) -> None:
    run = {
        "provider": "free",
        "model": model,
        "accuracy": accuracy,
        "hits": 15,
        "total": 30,
        "results": [],
    }
    if dataset:
        run["dataset"] = dataset
    path.write_text(json.dumps(run))


def test_benchmark_runs_stay_out_of_the_model_menu(tmp_path):
    run_file(tmp_path / "chinook.json", None, "m-chinook")
    run_file(tmp_path / "spider.json", "spider-dev-200", "m-spider")
    assert set(load_scores(tmp_path)) == {("free", "m-chinook")}


def test_compare_writes_each_dataset_into_its_own_block(tmp_path, monkeypatch, capsys):
    results = tmp_path / "results"
    results.mkdir()
    run_file(results / "a.json", None, "chinook-model", 0.9)
    run_file(results / "b.json", "spider-dev-200", "spider-model", 0.6)
    readme = tmp_path / "README.md"
    readme.write_text(
        "<!-- eval-table:start -->\nold\n<!-- eval-table:end -->\n"
        "<!-- eval-table:spider:start -->\nold\n<!-- eval-table:spider:end -->\n"
    )
    monkeypatch.setattr(compare, "RESULTS", results)
    monkeypatch.setattr(compare, "README", readme)
    monkeypatch.setattr(compare.update_readme, "__defaults__", (readme, "chinook"))
    assert compare.main(["--dataset", "spider-dev-200", "--readme"]) == 0
    text = readme.read_text()
    chinook, spider = text.split("<!-- eval-table:spider:start -->")
    assert "spider-model" in spider and "chinook-model" not in spider
    assert "old" in chinook
    assert compare.main(["--dataset", "bird-dev-100"]) == 1
