<div align="center">

# AskDB

**Ask your database questions in plain English and get validated, read-only, self-correcting SQL, with results and charts.**

[![CI](https://github.com/RithyBondeth/AskDB/actions/workflows/ci.yml/badge.svg)](https://github.com/RithyBondeth/AskDB/actions/workflows/ci.yml)

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Google_Gemini-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white)

</div>

<!-- Demo GIF: start the app with a model key, run `uv run scripts/record_demo.py`
     from the repo root, then replace this comment with ![AskDB demo](docs/demo.gif) -->

---

## Overview

AskDB is a natural-language-to-SQL agent. It turns a question into validated, read-only SQL and runs it. When the database returns an error, it fixes its own mistakes, then answers with a table, an automatically chosen chart, and a plain-language summary.

It works with a **free hosted model** by default (Google Gemini's free tier), with **Claude**, **Groq**, **OpenRouter**, and **OpenAI**, or with an **open-source model on your own machine** ([Arctic-Text2SQL-R1-7B](https://hf.co/Snowflake/Arctic-Text2SQL-R1-7B) or any Ollama model). You choose the provider and model for each question.

## Features

- **Your own data:** upload SQLite or CSV files, or connect a live PostgreSQL or MySQL database.
- **Read-only, enforced twice:** a sqlglot validator plus a read-only database session.
- **Self-correction:** database and validation errors go back to the model for up to two repairs, and you can inspect every attempt.
- **Live pipeline progress** streamed over Server-Sent Events.
- **Results:** sortable, filterable tables; bar, line, stacked-bar, pie and scatter charts; load-more paging; and full CSV export.
- **Plain-language answer** above every result.
- **Follow-up questions** in a chat thread, plus SQL editing and re-running.
- **History** saved on the server, with share links (`?a=` for answers, `?q=` for questions).
- **👍/👎 feedback** that becomes few-shot examples and eval cases.
- **Bring your own key:** keys stay in the browser and are never stored or logged by the server.
- **Schema linking** with BM25, and optionally embeddings, for large databases.
- **⌘K command palette,** a hand-drawn "doodle" UI, and light and dark themes.
- **Evaluation harness** for execution accuracy on Chinook, Spider, and BIRD.

## Tech Stack

| Area | Technology |
| --- | --- |
| Backend | Python 3.11+, FastAPI, SQLAlchemy, sqlglot, uv |
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS, Recharts |
| Models | Anthropic Claude, Google Gemini, Groq, OpenRouter, OpenAI, Ollama |
| Databases | SQLite (bundled Chinook sample), PostgreSQL, MySQL/MariaDB |
| Testing | Pytest, Ruff, Vitest, Playwright smoke tests, GitHub Actions |

## How It Works

```text
question
   │
   ▼
[1 schema introspection] ──► [2 schema linking: pick relevant tables]
   │
   ▼
[3 prompt: schema + few-shot examples + question] ──► model ──► SQL
   │
   ▼
[4 validate: one statement? read-only? parses?] ──┐ fail
   │ pass                                         │
   ▼                                              │
[5 execute on a read-only connection]             │
   │   error ─────────────────────────────────────┴──► error fed back to the model
   │ success                                           (up to 2 repairs)
   ▼
[6 present: summary + table + chart]
```

| Stage | Code |
| --- | --- |
| 1. Introspection | [`backend/askdb/schema.py`](backend/askdb/schema.py) |
| 2. Schema linking | [`backend/askdb/linking.py`](backend/askdb/linking.py) |
| 3. Generation | [`generate.py`](backend/askdb/generate.py), [`hosted.py`](backend/askdb/hosted.py), [`local.py`](backend/askdb/local.py), [`prompts.py`](backend/askdb/prompts.py) |
| 4. Validation | [`backend/askdb/validate.py`](backend/askdb/validate.py) |
| 5. Execute and self-correct | [`execute.py`](backend/askdb/execute.py), [`db.py`](backend/askdb/db.py) |
| 6. Presentation | [`backend/askdb/present.py`](backend/askdb/present.py) and the Next.js UI |

## Getting Started

### Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- A free [Gemini API key](https://aistudio.google.com/apikey), pasted into the app (an Anthropic key is optional)

### Installation

```bash
git clone https://github.com/RithyBondeth/AskDB.git
cd AskDB
```

**Backend** (port 8000):

```bash
cd backend
cp .env.example .env      # optional server-side keys
uv sync
uv run uvicorn api.main:app --reload --port 8000
```

**Frontend** (port 3000), in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The full guide, covering configuration, the open model, your own database, and troubleshooting, is in **[docs/RUNNING.md](docs/RUNNING.md)**.

### Optional: Open Model

```bash
ollama pull hf.co/mradermacher/Arctic-Text2SQL-R1-7B-GGUF:Q4_K_M   # 4.8 GB
```

Pick **Open model** in the UI, or set `ASKDB_PROVIDER=local`.

### Command Line

```bash
cd backend
uv run askdb "Which artist has the most albums?"
uv run askdb --provider local "How many tracks are in each genre?"
```

### Testing

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest -q
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

## API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/ask` | Question → SQL, explanation, rows, chart spec, and every attempt |
| `POST` | `/api/ask/stream` | Same as `/api/ask`, streamed as Server-Sent Events |
| `POST` | `/api/run` | Run edited SQL behind the same read-only validation |
| `POST` | `/api/rows` | Next page of an answer's rows |
| `POST` | `/api/export` | Every row as streamed CSV |
| `GET` / `POST` / `DELETE` | `/api/databases` | List, upload, or delete databases |
| `POST` | `/api/databases/connect` | Connect a live PostgreSQL or MySQL database |
| `GET` / `DELETE` | `/api/history` | Saved answers |
| `POST` | `/api/history/{id}/share` | Share a saved answer |
| `POST` | `/api/feedback` | Store 👍/👎 feedback |
| `GET` | `/api/schema` | Tables, columns, and suggested questions |
| `POST` | `/api/keys/check` | Check that a model key works |
| `GET` | `/api/health` | Status, dialect, and available models |

The user's own model key travels in the `X-AskDB-Api-Key` header and overrides the server key for that request.

## Evaluation

Execution accuracy on 35 Chinook questions (`eval/compare.py --readme` regenerates this table):

<!-- eval-table:start -->
| Model | Provider | Execution accuracy | Fixed by self-correction | Median s/question |
| --- | --- | --- | --- | --- |
| `gemini-flash-latest` | free | _not measured yet_ | | |
| `claude-opus-5-5` | claude | _not measured yet_ | | |
| `Arctic-Text2SQL-R1-7B` (Q4_K_M) | local | _not measured yet_ | | |
<!-- eval-table:end -->

```bash
cd backend
uv run python eval/run_eval.py --limit 5                                   # smoke run
uv run python eval/run_eval.py --delay 5 --out eval/results/gemini-free.json
uv run python eval/run_eval.py --provider claude --out eval/results/claude-opus-5-5.json
uv run python eval/compare.py --readme
```

A prediction counts as correct when it returns the same rows as the gold query. Row order is ignored unless the item is marked as ordered, column order doesn't matter, and floats are rounded to two decimal places.

### Standard Benchmarks

`eval/benchmarks.py` turns the [Spider](https://yale-lily.github.io/spider) or [BIRD](https://bird-bench.github.io) dev set into a reproducible subset. These runs use AskDB's own matching rules, so they are comparable across AskDB runs but not identical to the official leaderboard metrics.

```bash
uv run python eval/benchmarks.py spider --source ~/data/spider --limit 200
uv run python eval/run_eval.py --dataset eval/benchmarks/spider-dev-200.jsonl --delay 5 \
    --out eval/results/spider-gemini-free.json
uv run python eval/compare.py --dataset spider-dev-200 --readme
```

**Spider dev** (subset):

<!-- eval-table:spider:start -->
| Model | Provider | Execution accuracy | Fixed by self-correction | Median s/question |
| --- | --- | --- | --- | --- |
| _not measured yet_ | | | | |
<!-- eval-table:spider:end -->

**BIRD dev** (subset):

<!-- eval-table:bird:start -->
| Model | Provider | Execution accuracy | Fixed by self-correction | Median s/question |
| --- | --- | --- | --- | --- |
| _not measured yet_ | | | | |
<!-- eval-table:bird:end -->

## Security Notes

- **Read-only, enforced twice:** the validator accepts exactly one `SELECT`-style statement and blocks functions that act instead of read (changing settings with `set_config`, sleeping, signalling or locking other sessions, reading server files, large objects, `dblink`, and SQLite's `load_extension`). The connection itself is also read-only (SQLite `mode=ro`, PostgreSQL `default_transaction_read_only`, a read-only MySQL session).
- **Bounded queries:** per-statement timeouts and row caps.
- **Untrusted uploads:** SQLite header and `PRAGMA quick_check` validation, `trusted_schema = OFF`, and size and count limits.
- **Per-browser isolation** for uploads and history. This is isolation, not authentication. Set `ASKDB_ALLOW_UPLOADS=false` on public demos.
- **No surprise bills:** visitors using the server's key can only choose operator-approved models.
- On PostgreSQL, connect as a dedicated low-privilege role ([setup](docs/RUNNING.md#a-postgresql-role-for-askdb)).

## Project Structure

```text
AskDB/
├── backend/
│   ├── askdb/        # Pipeline: schema, linking, prompts, generation, validation,
│   │                 # execution, presentation, providers, uploads, storage
│   ├── api/main.py   # FastAPI app
│   ├── data/         # Bundled Chinook sample database
│   ├── eval/         # Datasets, eval runner, benchmarks, comparison
│   └── tests/        # Pytest suite
├── frontend/
│   ├── src/app/      # Page and API route handlers (proxy to the backend)
│   ├── src/components/
│   ├── src/lib/      # Streaming, formatting, keys, with Vitest tests
│   └── e2e/          # Playwright smoke tests
├── scripts/          # Demo recording
└── docs/RUNNING.md   # Full setup guide
```

## Credits

Illustrations are from [Open Doodles](https://www.opendoodles.com) by Pablo Stanley ([CC0](https://creativecommons.org/publicdomain/zero/1.0/)), adapted from [react-open-doodles](https://github.com/lunahq/react-open-doodles) (MIT).

## Author

**Rithy Bondeth** — Full Stack Developer & AI Engineer

[![Portfolio](https://img.shields.io/badge/Portfolio-0A0A0A?style=for-the-badge&logo=vercel&logoColor=white)](https://bondeth.dev)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/RithyBondeth)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/rithy-bondeth-484073282/)

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.
