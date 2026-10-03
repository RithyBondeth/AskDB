# Running AskDB

This guide takes you from a fresh clone to a working app. It covers setup,
day-to-day commands, the optional open-source model, configuration, and
troubleshooting.

AskDB has two parts that run at the same time:

| Part | Folder | Port | What it does |
| --- | --- | --- | --- |
| Backend | `backend/` | 8000 | Python API: writes, validates, and runs the SQL |
| Frontend | `frontend/` | 3000 | Next.js web UI you open in the browser |

The browser only talks to the frontend, which forwards requests to the backend.
You need **two terminals**, one for each part.

---

## 1. Prerequisites

| Tool | Version | Check with |
| --- | --- | --- |
| Python | 3.11 or newer | `python3 --version` |
| [uv](https://docs.astral.sh/uv/) | any recent | `uv --version` |
| Node.js | 20 or newer | `node --version` |
| Git | any | `git --version` |

**Install uv** if you don't have it:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**A model to generate SQL.** You need at least one of these:

- **Claude** (recommended, fastest): an Anthropic API key from
  [platform.claude.com](https://platform.claude.com/). Each question costs a
  small amount of API credit.
- **Open model** (free, runs offline): [Ollama](https://ollama.com) and about
  6 GB of free RAM. See [section 5](#5-optional-run-the-open-source-model).

---

## 2. Get the code

```bash
git clone https://github.com/RithyBondeth/AskDB.git
cd AskDB
git checkout bondeth/fervent-fermat-ua5zok   # until this branch is merged into main
```

---

## 3. First-time setup

### Backend

```bash
cd backend
cp .env.example .env        # Windows: copy .env.example .env
uv sync                     # creates .venv and installs dependencies
```

Open `backend/.env` in an editor and set your key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

No key? Set `ASKDB_PROVIDER=local` instead and follow
[section 5](#5-optional-run-the-open-source-model).

### Frontend

```bash
cd frontend
cp .env.example .env.local  # Windows: copy .env.example .env.local
npm install
```

The default `.env.local` points the frontend at `http://127.0.0.1:8000`, which
is where the backend runs. You don't need to change it.

---

## 4. Start the app

**Terminal 1, backend:**

```bash
cd backend
uv run uvicorn api.main:app --reload --port 8000
```

Check it at http://localhost:8000/api/health. You should see something like:

```json
{"status": "ok", "dialect": "sqlite", "tables": 11, "default_provider": "claude", ...}
```

**Terminal 2, frontend:**

```bash
cd frontend
npm run dev
```

Open **http://localhost:3000**. Click an example question or type your own,
for example *"Which artist has the most albums?"*

To stop either part, press `Ctrl+C` in its terminal.

### What you can do

- **Ask, then follow up.** Answers stack up as a conversation, and follow-ups
  such as "only for 2012" build on the earlier queries. **New chat** starts over.
- **Watch it work.** The Generate → Validate → Execute → Present steps update
  live. A failed attempt shows as "self-correcting", and you can expand it
  afterwards to see what went wrong.
- **Explore the result.** Switch between Chart, Table, and SQL. Click a column
  header to sort, filter rows, switch bar/line, or download CSV.
- **Edit the SQL.** In the SQL tab, click **Edit**, change the query, and press
  **Run** (or `⌘↵`). It is still validated as read-only. **Revert** brings back
  the model's version.
- **Use the keyboard.** `⌘K` (`Ctrl+K` on Windows/Linux) opens the command
  palette, and `/` jumps to the question box.
- **Share.** **Share** copies a link like `http://localhost:3000/?q=...` that
  asks the same question when opened.
- **Build questions from the schema.** Click a table or column in the sidebar
  (the panel button on mobile) to insert its name into your question.

---

## 5. Optional: run the open-source model

AskDB can use [Arctic-Text2SQL-R1-7B](https://hf.co/Snowflake/Arctic-Text2SQL-R1-7B),
an open, Apache-2.0 text-to-SQL model, running on your own machine through Ollama.

1. Install Ollama from https://ollama.com and start it.
2. Download the model (4.8 GB, one time only):

   ```bash
   ollama pull hf.co/mradermacher/Arctic-Text2SQL-R1-7B-GGUF:Q4_K_M
   ```

3. In the web UI, switch the toggle under the question box to **Open model**.

To make the open model the default, add this to `backend/.env` and restart the
backend:

```
ASKDB_PROVIDER=local
```

**What to expect:**

- It is slower than Claude, because it writes out its reasoning before the SQL.
  On a laptop without a GPU, one question can take a minute or more.
- Low on RAM? Pull a smaller version and point AskDB at it:

  ```bash
  ollama pull hf.co/mradermacher/Arctic-Text2SQL-R1-7B-GGUF:Q3_K_M   # 3.9 GB
  ```

  ```
  # backend/.env
  ASKDB_LOCAL_MODEL=hf.co/mradermacher/Arctic-Text2SQL-R1-7B-GGUF:Q3_K_M
  ```

- To use vLLM, llama.cpp, or LM Studio instead of Ollama, set
  `ASKDB_LOCAL_API=openai` and `ASKDB_LOCAL_BASE_URL` to that server's address.

---

## 6. Use your own data

Click the database name at the top left (next to the AskDB logo), then
**Upload your data…**. You can also click **Use your own data** on the home
screen, or press `⌘K` and choose **Upload your data…**.

- **SQLite:** one `.db`, `.sqlite`, `.sqlite3`, or `.db3` file.
- **CSV:** one or more `.csv` (or `.tsv`) files. Each file becomes a table named
  after the file, so `orders.csv` and `customers.csv` give you `orders` and
  `customers` tables that you can join. Column names are converted to
  `snake_case` (`Order Date` → `order_date`). Number columns are detected
  automatically, and empty cells become NULL.

After the upload, AskDB switches to the new database, shows its schema, and
suggests a few starter questions. Switch between databases with the same menu,
and delete an upload with the trash icon that appears when you hover over it.
Switching database starts a new chat.

Uploads are stored in `backend/data/uploads/` (ignored by git) and survive
restarts. They're opened read-only, so AskDB can't change them.

Limits are set in `backend/.env`:

| Variable | Default | What it does |
| --- | --- | --- |
| `ASKDB_ALLOW_UPLOADS` | `true` | Set `false` to turn uploads off, for example on a public demo |
| `ASKDB_MAX_UPLOAD_MB` | `50` | Maximum total size of one upload |
| `ASKDB_MAX_UPLOADS` | `20` | Maximum number of stored uploads |
| `ASKDB_UPLOAD_DIR` | `data/uploads` | Where uploads are stored |

There are no user accounts. Anyone who can open your AskDB can see and query
every upload, so don't upload sensitive data to a shared server.

---

## 7. Use it from the terminal (no UI)

From `backend/`:

```bash
uv run askdb "Which artist has the most albums?"
uv run askdb --show-schema "Total revenue per year"
uv run askdb --provider local "How many tracks are in each genre?"
```

Only the backend's dependencies are needed for this. The web servers don't
have to be running.

---

## 8. Tests and checks

**Backend** (no API key or network needed):

```bash
cd backend
uv run pytest            # all tests
uv run ruff check .      # lint
uv run ruff format .     # auto-format
```

**Frontend:**

```bash
cd frontend
npm run lint
npm run build            # production build; catches type errors
```

---

## 9. Measure accuracy (evaluation)

The eval runs every question in `backend/eval/dataset.jsonl` through the full
pipeline. It counts a question as correct when the generated query returns the
same rows as the reference query.

```bash
cd backend
uv run python eval/run_eval.py --limit 5        # quick smoke run, 5 questions

# Full runs, saved for comparison
uv run python eval/run_eval.py --out eval/results/claude-opus-5-5.json
uv run python eval/run_eval.py --provider local --out eval/results/arctic-7b-q4.json

# Markdown table for the README, plus the questions where the models disagree
uv run python eval/compare.py
```

Claude runs use API credits. Local runs are free but slower. Commit the files
in `eval/results/` so you can track accuracy over time.

To add questions, append lines to `eval/dataset.jsonl`:

```json
{"id": "short-unique-id", "question": "Plain English question", "gold_sql": "SELECT ...", "ordered": false}
```

Set `"ordered": true` only when row order matters, for example "top 5 ...".

---

## 10. Configuration reference

All settings go in `backend/.env`. Every one is optional except a model source.

| Variable | Default | What it does |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | none | Key for Claude |
| `ASKDB_PROVIDER` | `claude` | Default model: `claude` or `local` |
| `ASKDB_MODEL` | `claude-opus-5-5` | Claude model ID |
| `ASKDB_EFFORT` | `medium` | Claude effort: `low`, `medium`, `high`, `xhigh`, `max` |
| `ASKDB_LOCAL_MODEL` | `hf.co/mradermacher/Arctic-Text2SQL-R1-7B-GGUF:Q4_K_M` | Open model name, as Ollama knows it |
| `ASKDB_LOCAL_BASE_URL` | `http://localhost:11434` | Where Ollama (or another server) runs |
| `ASKDB_LOCAL_API` | `ollama` | `ollama`, or `openai` for `/v1/completions` servers |
| `ASKDB_LOCAL_TIMEOUT_S` | `600` | Seconds to wait for the open model |
| `ASKDB_DATABASE_URL` | bundled `data/chinook.sqlite` | Database to query (SQLAlchemy URL) |
| `ASKDB_MAX_RETRIES` | `2` | Self-correction attempts after the first try |
| `ASKDB_ROW_LIMIT` | `100` | Maximum rows returned |
| `ASKDB_STATEMENT_TIMEOUT_S` | `10` | Seconds before a query is cancelled |
| `ASKDB_REFERENCE_DATE` | `2013-12-31` | "Today" for relative dates; set it empty for live data |
| `ASKDB_CORS_ORIGINS` | `["http://localhost:3000"]` | Origins allowed to call the API directly |
| `ASKDB_ALLOW_UPLOADS` | `true` | Allow uploading SQLite/CSV databases ([section 6](#6-use-your-own-data)) |
| `ASKDB_MAX_UPLOAD_MB` | `50` | Maximum size of one upload |
| `ASKDB_MAX_UPLOADS` | `20` | Maximum number of stored uploads |

Frontend setting, in `frontend/.env.local`:

| Variable | Default | What it does |
| --- | --- | --- |
| `ASKDB_API_URL` | `http://127.0.0.1:8000` | Where the frontend finds the backend |

### Using your own database

Point `ASKDB_DATABASE_URL` at it and restart the backend:

```
# SQLite file
ASKDB_DATABASE_URL=sqlite:////absolute/path/to/my.db

# PostgreSQL (first run: uv add "psycopg[binary]")
ASKDB_DATABASE_URL=postgresql+psycopg://readonly_user:password@localhost:5432/mydb
```

Also:

- Set `ASKDB_REFERENCE_DATE=` (empty) so relative dates use the real today.
- Replace the Chinook examples in `backend/askdb/prompts.py` with a few
  question/SQL pairs for your own schema. This noticeably improves accuracy.
- For PostgreSQL, use a database user that only has read access. AskDB already
  opens the connection read-only, but a read-only user is a sensible extra layer.

The open model is trained on SQLite, so expect it to do better on SQLite
databases than on PostgreSQL.

---

## 11. Troubleshooting

| Problem | Likely cause and fix |
| --- | --- |
| `No Anthropic credentials found` | `ANTHROPIC_API_KEY` is missing from `backend/.env`, or you started the backend before saving it. Fix the file and restart the backend. |
| `Anthropic API key is missing or invalid` | The key is wrong or revoked. Create a new one. |
| `Cannot reach the AskDB API at http://127.0.0.1:8000` | The backend isn't running. Start it in terminal 1. |
| Schema sidebar says "Backend unreachable" | Same as above. |
| `Cannot reach the open model server` | Ollama isn't running. Start the Ollama app, or run `ollama serve`. |
| Open model error mentioning "model not found" | You haven't pulled the model, or `ASKDB_LOCAL_MODEL` doesn't match the name you pulled. Run `ollama list` to check. |
| `The open model timed out` | Your machine is too slow for this size. Use the `Q3_K_M` version, or raise `ASKDB_LOCAL_TIMEOUT_S`. |
| `Rate limited by the model API` | Too many requests too fast. Wait a moment and try again. |
| `address already in use` | Another program is using port 8000 or 3000. Close it, or start on another port: `--port 8001` for the backend (then update `ASKDB_API_URL`), or `npm run dev -- -p 3001` for the frontend. |
| `uv: command not found` | uv isn't installed, or your terminal hasn't picked it up. Install it (section 1), then open a new terminal. |
| `Could not answer after 3 attempts` | The model couldn't write a working query. The UI shows each attempt and its error. Try rephrasing the question more specifically. |
| `Blocked: Only SELECT queries are allowed` | Working as intended. AskDB never runs queries that change data. |
| `This isn't a SQLite database file.` | The file has a `.db`/`.sqlite` name but isn't SQLite. Export it as SQLite, or as CSV. |
| `Upload limit reached` | Delete an old upload from the database menu, or raise `ASKDB_MAX_UPLOADS`. |
| `needs a header row and at least one data row` | The CSV's first line must be column names, followed by data. |
| `That database no longer exists.` | Someone deleted the upload. Pick another database from the menu. |

Still stuck? Run the backend tests (`uv run pytest`). If they pass, the backend
code is fine and the problem is in configuration or the model connection.
