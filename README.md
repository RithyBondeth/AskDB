# AskDB

**Ask your database questions in plain English.** AskDB turns a question into
validated, read-only SQL, runs it, fixes its own mistakes when the database
returns an error, and answers with a table and an automatically chosen chart.

> Demo GIF goes here: question → answer → self-correction.

**Execution accuracy:** _not measured yet_. Run `uv run python eval/run_eval.py`
and put the number here (see [Evaluation](#evaluation)).

## How it works

```
question
   │
   ▼
[1 schema introspection] ──► [2 schema linking: pick relevant tables]
   │
   ▼
[3 prompt: schema + few-shot examples + question] ──► Claude ──► SQL
   │
   ▼
[4 validate: one statement? read-only? parses?] ──┐ fail
   │ pass                                         │
   ▼                                              │
[5 execute on a read-only connection]             │
   │   error ─────────────────────────────────────┴──► error fed back to the model
   │ success                                           (up to 2 repairs)
   ▼
[6 present: table + bar/line chart]
```

| Stage | Code |
| --- | --- |
| 1. Introspection | [`backend/askdb/schema.py`](backend/askdb/schema.py) `introspect` |
| 2. Schema linking | [`backend/askdb/schema.py`](backend/askdb/schema.py) `link_tables` |
| 3. Generation | [`backend/askdb/generate.py`](backend/askdb/generate.py), [`prompts.py`](backend/askdb/prompts.py) |
| 4. Validation | [`backend/askdb/validate.py`](backend/askdb/validate.py) |
| 5. Execute + self-correct | [`backend/askdb/execute.py`](backend/askdb/execute.py), [`db.py`](backend/askdb/db.py) |
| 6. Presentation | [`backend/askdb/present.py`](backend/askdb/present.py) + the Next.js UI |

## Stack

| Layer | Choice |
| --- | --- |
| Database | SQLite with the bundled [Chinook](https://github.com/lerocha/chinook-database) sample (Postgres supported via `ASKDB_DATABASE_URL`) |
| LLM | Claude (`claude-opus-5-5`) through the Anthropic Python SDK |
| DB access | SQLAlchemy |
| SQL parsing | sqlglot |
| API | FastAPI |
| UI | Next.js (App Router) + Tailwind + Recharts |
| Eval | Execution accuracy on question → gold-SQL pairs |

## Run it locally

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node 20+, and an
[Anthropic API key](https://platform.claude.com/).

**Backend** (port 8000):

```bash
cd backend
cp .env.example .env          # add your ANTHROPIC_API_KEY
uv sync
uv run uvicorn api.main:app --reload --port 8000
```

**Frontend** (port 3000), in a second terminal:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000.

**Command line**, without the UI:

```bash
cd backend
uv run askdb "Which artist has the most albums?"
uv run askdb --show-schema "Revenue per year"
```

**Tests:**

```bash
cd backend && uv run pytest
cd frontend && npm run lint && npm run build
```

## API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/ask` | `{"question": "..."}` → SQL, explanation, columns, rows, chart spec, and every attempt |
| `GET` | `/api/schema` | Tables and columns |
| `GET` | `/api/health` | Status, dialect, and table count |

When every attempt fails, `/api/ask` returns 422 with the failed attempts, so the
UI can show what was tried.

## Design decisions

**Read-only, enforced twice.** Model output never runs unchecked.
`validate.py` parses the SQL with sqlglot and accepts exactly one `SELECT` or
`UNION`/`INTERSECT`/`EXCEPT` statement. It rejects stacked statements and
anything containing writes, DDL, `PRAGMA`, `ATTACH`, `SELECT INTO`, or
`FOR UPDATE`. Separately, the database connection is opened read-only (SQLite
`mode=ro`, Postgres `default_transaction_read_only`), so a statement the parser
misses still can't change data. `tests/test_validate.py` and
`tests/test_execute.py` check both layers.

**Self-correction.** Database errors (unknown column, bad join) *and*
validation failures (syntax errors, blocked statements) are sent back to the
model with the failed SQL, up to `ASKDB_MAX_RETRIES` (default 2) repairs.
Blocked SQL gets a chance to be rewritten as a safe query but is never executed.

**Bounded queries.** Each statement has a timeout (SQLite through a progress
handler, Postgres through `statement_timeout`) and results are capped at
`ASKDB_ROW_LIMIT` rows.

**Schema linking.** Chinook has 11 tables, so the whole schema goes into the
prompt. Above 15 tables, `link_tables` picks the relevant tables and their
foreign-key neighbours with a keyword score. Embedding-based retrieval is the
planned v2.

**Fixed reference date.** Chinook's invoices end in December 2013, so relative
questions like "last quarter" are resolved against `ASKDB_REFERENCE_DATE`
(default `2013-12-31`). Set it to empty for live data.

**Prompt caching.** The system prompt (schema plus examples) is the same for
every question, so it is cached. Only the question changes between requests.

## Evaluation

`backend/eval/dataset.jsonl` holds question → gold-SQL pairs for Chinook. The
harness runs each question through the full pipeline and checks whether the
predicted query returns the same rows as the gold query:

- Row order is ignored unless the item is marked `"ordered": true`.
- Column order doesn't matter, and extra columns are allowed.
- Floats are rounded to 2 decimal places, and NULLs are handled.
- Both queries are compared on their full results, not the row-capped ones.

```bash
cd backend
uv run python eval/run_eval.py --limit 5                 # smoke run
uv run python eval/run_eval.py --out eval/results/v1.json
```

Each run makes real API calls. Commit the results files to track accuracy
across prompt and model changes. The dataset has 15 items and the target is
30–50.

## Project layout

```
backend/
  askdb/           pipeline: schema, prompts, generate, validate, execute, present
  api/main.py      FastAPI app
  data/            chinook.sqlite (bundled sample, opened read-only)
  eval/            dataset.jsonl + run_eval.py
  tests/           pytest suite (no network needed)
frontend/
  src/app/         page + API route handlers (proxy to the backend)
  src/components/  question box, attempts, table, chart, schema panel
```

## Roadmap

- [x] Week 1: sample DB, introspection, end-to-end generate-and-run
- [x] Week 2: read-only validation, timeouts, self-correction loop, tests
- [x] Week 3: web UI with table and automatic chart, few-shot prompt
- [ ] Week 4: grow the eval set, record accuracy, demo GIF, deploy
- [ ] Stretch: embedding-based schema linking, an open Hugging Face SQL model
      for comparison, point it at your own data
