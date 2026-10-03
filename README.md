# AskDB

**Ask your database questions in plain English.** AskDB turns a question into
validated, read-only SQL, runs it, fixes its own mistakes when the database
returns an error, and answers with a table and an automatically chosen chart.

> Demo GIF goes here: question → answer → self-correction.

**Features:** upload your own data (SQLite or CSV) · follow-up questions in a chat thread · live pipeline progress
(streamed) · self-correction you can inspect · edit and re-run the SQL ·
sortable, filterable results with bar/line charts and CSV export · ⌘K command
palette · share links (`?q=`) · light and dark themes.

Works with **Claude** or an **open-source model running on your own machine**
([Arctic-Text2SQL-R1-7B](https://hf.co/Snowflake/Arctic-Text2SQL-R1-7B) via
Ollama). Switch between them per question in the UI.

**Execution accuracy:** _not measured yet_. See [Evaluation](#evaluation).

| Model | Execution accuracy | Fixed by self-correction | Median s/question |
| --- | --- | --- | --- |
| `claude-opus-5-5` | _run the eval_ | | |
| `Arctic-Text2SQL-R1-7B` (Q4_K_M, local) | _run the eval_ | | |

## How it works

```
question
   │
   ▼
[1 schema introspection] ──► [2 schema linking: pick relevant tables]
   │
   ▼
[3 prompt: schema + few-shot examples + question] ──► Claude or open model ──► SQL
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
| 3. Generation | Claude: [`backend/askdb/generate.py`](backend/askdb/generate.py), [`prompts.py`](backend/askdb/prompts.py). Open model: [`backend/askdb/local.py`](backend/askdb/local.py) |
| 4. Validation | [`backend/askdb/validate.py`](backend/askdb/validate.py) |
| 5. Execute + self-correct | [`backend/askdb/execute.py`](backend/askdb/execute.py), [`db.py`](backend/askdb/db.py) |
| 6. Presentation | [`backend/askdb/present.py`](backend/askdb/present.py) + the Next.js UI |

## Stack

| Layer | Choice |
| --- | --- |
| Database | SQLite with the bundled [Chinook](https://github.com/lerocha/chinook-database) sample (Postgres supported via `ASKDB_DATABASE_URL`) |
| LLM | Claude (`claude-opus-5-5`) through the Anthropic Python SDK, or [Arctic-Text2SQL-R1-7B](https://hf.co/Snowflake/Arctic-Text2SQL-R1-7B) (open, Apache-2.0) served by Ollama |
| DB access | SQLAlchemy |
| SQL parsing | sqlglot |
| API | FastAPI |
| UI | Next.js (App Router) + Tailwind + Recharts, with a hand-drawn "doodle" design and [Open Doodles](https://www.opendoodles.com) illustrations |
| Eval | Execution accuracy on question → gold-SQL pairs |

## Run it locally

> The full guide, covering configuration, the open model, your own database,
> and troubleshooting, is in **[docs/RUNNING.md](docs/RUNNING.md)**. Quick version:

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

**Open model** (optional, free, runs offline). Install [Ollama](https://ollama.com), then:

```bash
ollama pull hf.co/mradermacher/Arctic-Text2SQL-R1-7B-GGUF:Q4_K_M   # 4.8 GB
```

Pick **Open model** in the UI, or set `ASKDB_PROVIDER=local` to make it the
default. A 7B model at 4-bit needs about 6 GB of free RAM. It is slow on CPU,
because it reasons step by step before answering. On a weak laptop, use
`:Q3_K_M` (3.9 GB), or try
[XiYanSQL-QwenCoder-3B](https://hf.co/XGenerationLab/XiYanSQL-QwenCoder-3B-2504).
To use vLLM, llama.cpp, or LM Studio instead of Ollama, set
`ASKDB_LOCAL_API=openai` and `ASKDB_LOCAL_BASE_URL` to the server.

**Command line**, without the UI:

```bash
cd backend
uv run askdb "Which artist has the most albums?"
uv run askdb --show-schema "Revenue per year"
uv run askdb --provider local "How many tracks are in each genre?"
```

**Tests:**

```bash
cd backend && uv run pytest
cd frontend && npm run lint && npm run build
```

## API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/ask` | `{"question": "...", "provider": "claude" \| "local", "context": [{"question", "sql"}]}` → SQL, explanation, columns, rows, chart spec, every attempt, and the model that answered. `provider`, `context` (up to 5 earlier turns, for follow-ups), and `database` (an upload's id; default is the sample) are optional. `/api/run` also takes `database` |
| `POST` | `/api/ask/stream` | Same request as `/api/ask`, answered as Server-Sent Events: `stage`, `generated`, `attempt_failed` while it runs, then `result` or `error` |
| `POST` | `/api/run` | `{"sql": "..."}` → runs SQL you edited, behind the same read-only validation |
| `GET` | `/api/schema?database=` | Tables, columns (with primary keys), and suggested questions |
| `GET` | `/api/databases` | The sample plus uploaded databases, and the upload limits |
| `POST` | `/api/databases` | Multipart `files` (one SQLite file, or CSVs) and optional `name` → a new database |
| `DELETE` | `/api/databases/{id}` | Delete an upload |
| `GET` | `/api/health` | Status, dialect, table count, and available models |

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

**Open model with its own prompt.** Small SQL models are very sensitive to the
prompt (the Arctic paper reports large gains from the prompt format alone).
`local.py` therefore reproduces the prompt from Snowflake's official evaluation
code: the OmniSQL instruction, ChatML, a `<think>` pre-fill, and taking the last
```` ```sql ```` block. It sends this raw so Ollama doesn't add a second chat
template, and uses greedy decoding to match how the benchmark numbers were
measured. The model was trained single-turn, so failed attempts for
self-correction go into the question instead of a chat history. The validator,
read-only connection, and retry loop are shared with Claude, so both models get
the same safety guarantees.

**Uploads are untrusted.** A SQLite upload must start with the SQLite file
header and pass `PRAGMA quick_check`. CSVs are parsed into a new database that
AskDB creates itself, with column types inferred and names converted to
`snake_case`. Every SQLite connection sets `trusted_schema = OFF`, so functions
named in a malicious schema don't run, and is opened read-only. Size and count
limits apply. Database ids are checked against a strict pattern, so they can't
be used to reach other files. Uploads get no Chinook few-shot examples, and
"today" is the real date. There are no user accounts, so every user of a
server sees every upload: set `ASKDB_ALLOW_UPLOADS=false` on a public demo.

**Follow-ups.** The UI sends the last three answered questions and their SQL
as `context`. Claude sees them as earlier conversation turns. The open model is
single-turn, so they go into its prompt as "earlier in this conversation".
Schema linking also uses the earlier questions, so a follow-up keeps the
tables it builds on.

**Edited SQL is not trusted either.** `/api/run` uses the same validator and
read-only connection as generated SQL, so editing a query can't be used to
write to the database.

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
uv run python eval/run_eval.py --limit 5                                   # smoke run
uv run python eval/run_eval.py --out eval/results/claude-opus-5-5.json
uv run python eval/run_eval.py --provider local --out eval/results/arctic-7b-q4.json
uv run python eval/compare.py      # Markdown table for the README + questions where they differ
```

Claude runs make real API calls. Local runs are free but slower. Commit the
results files to track accuracy across prompt and model changes. The dataset has 15 items and the target is
30–50.

## Project layout

```
backend/
  askdb/           pipeline: schema, prompts, generate (Claude), local (open model),
                   validate, execute, present; sources + importers (uploads)
  api/main.py      FastAPI app
  data/            chinook.sqlite (bundled sample) and uploads/ (git-ignored)
  eval/            dataset.jsonl, run_eval.py, compare.py
  tests/           pytest suite (no network needed)
frontend/
  src/app/         page + API route handlers (proxy to the backend)
  src/components/  question box, attempts, table, chart, schema panel
```

## Credits

Illustrations are from [Open Doodles](https://www.opendoodles.com) by
[Pablo Stanley](https://twitter.com/pablostanley), released under
[CC0](https://creativecommons.org/publicdomain/zero/1.0/). The SVGs were taken
from [react-open-doodles](https://github.com/lunahq/react-open-doodles) (MIT),
minified, and recolored to match the theme (`frontend/src/lib/doodles.ts`).

## Roadmap

- [x] Week 1: sample DB, introspection, end-to-end generate-and-run
- [x] Week 2: read-only validation, timeouts, self-correction loop, tests
- [x] Week 3: web UI with table and automatic chart, few-shot prompt
- [x] Open model: Arctic-Text2SQL-R1-7B via Ollama, switchable per question
- [x] Upload your own data: SQLite files or CSVs
- [ ] Week 4: grow the eval set, record Claude vs. open-model accuracy, demo GIF, deploy
- [ ] Stretch: embedding-based schema linking, point it at your own data
