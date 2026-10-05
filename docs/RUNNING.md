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

**A model to generate SQL.** The default is free:

- **Free model (default):** a free Google Gemini API key from
  [aistudio.google.com/apikey](https://aistudio.google.com/apikey). Sign in with
  a Google account and click **Create API key**. No credit card needed.
- **Claude** (optional, most accurate): an Anthropic API key from
  [platform.claude.com](https://platform.claude.com/). Each question costs a
  small amount of API credit.
- **Open model** (optional, free, runs offline): [Ollama](https://ollama.com)
  and about 6 GB of free RAM. See [section 5](#5-optional-run-the-open-source-model).

---

## 2. Get the code

```bash
git clone https://github.com/RithyBondeth/AskDB.git
cd AskDB
```

---

## 3. First-time setup

### Backend

```bash
cd backend
cp .env.example .env        # Windows: copy .env.example .env
uv sync                     # creates .venv and installs dependencies
```

You don't have to put a key in `.env`. Once the app is running, click
**Add API key** on the home screen (or the key button in the top bar) and paste
your free Gemini key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
**Test** checks it without using any quota. The key is saved only in your
browser and sent with each question; the backend uses it for that request and
never stores or logs it. Each person who opens the app adds their own key. An
Anthropic key for Claude goes in the same dialog.

**Optional: a server key.** If you'd rather everyone (or just you) use one key
without typing it, put it in `backend/.env` and restart the backend:

```
ASKDB_FREE_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...   # only for Claude
```

A key a user adds in the browser always takes precedence over the server's. Be
careful with a server key on a public deployment: every visitor spends it.

**Other providers.** Groq, OpenRouter and OpenAI are built in: pick one in the
menu under the question box and add its key under **API keys**. Each also takes
a server key (`ASKDB_GROQ_API_KEY`, `ASKDB_OPENROUTER_API_KEY`,
`ASKDB_OPENAI_API_KEY`). For another OpenAI-compatible service, such as
LM Studio, point the free provider at it:

```
ASKDB_FREE_BASE_URL=http://localhost:1234/v1
ASKDB_FREE_MODEL=the-model-you-loaded
```

To see which models a provider offers your server key:

```bash
uv run askdb --list-models                     # the free provider
uv run askdb --list-models --provider groq
```

**Choosing a model.** Next to the provider menu is a model menu:

- **With your own key** (added in the app), it lists every chat model that key
  can use, fetched live from the provider. For Claude: Opus 5.5 (default),
  Sonnet 5.5, Haiku 4.5 and Fable 5.1.
- **With the server's key**, it lists only the models allowed in `backend/.env`,
  so visitors can't run up the bill on an expensive model. The defaults allow
  each provider's default model, plus Claude Sonnet and Haiku, which cost less
  than Opus. To allow more:

  ```
  ASKDB_CLAUDE_MODELS=["claude-opus-5-5","claude-sonnet-5-5","claude-haiku-4-5","claude-fable-5-1"]
  ASKDB_GROQ_MODELS=["openai/gpt-oss-120b","llama-3.3-70b-versatile"]
  ```
- **For the open model**, it lists the models installed in Ollama (`ollama list`).

The app remembers your provider and model in this browser.

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
- **Pick a model.** Under the question box, choose the provider (Free/Gemini,
  Claude, Groq, OpenRouter, OpenAI, or the local open model) and then the exact
  model. Your own key unlocks every model the provider offers you.
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
| `ASKDB_MAX_UPLOADS` | `20` | Maximum number of uploads each browser can keep |
| `ASKDB_MAX_TOTAL_UPLOADS` | `200` | Maximum number of uploads on the server, across everyone |
| `ASKDB_UPLOAD_DIR` | `data/uploads` | Where uploads are stored |

Your uploads are private to your browser. There are no accounts: the app gives
your browser a random id (kept in `localStorage`), and only requests carrying that
id can see, query, or delete your uploads. Other people using the same server
can't see them. Two things follow:

- Opening AskDB in another browser, a private window, or after clearing site data
  gives you a new id, and your earlier uploads won't appear there. They stay on
  the server until deleted from `backend/data/uploads/`.
- The id isn't a password. Anyone with access to your browser profile can read it,
  so still don't upload sensitive data to a server you don't control.

Uploads made with an older version of AskDB have no owner and stay visible to
everyone.

---

## 7. Use it from the terminal (no UI)

From `backend/`:

```bash
uv run askdb "Which artist has the most albums?"
uv run askdb --show-schema "Total revenue per year"
uv run askdb --provider local "How many tracks are in each genre?"
uv run askdb --provider claude "Revenue per year"
uv run askdb --list-models          # models your free-model key can use
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
uv run python eval/run_eval.py --delay 5 --out eval/results/gemini-free.json
uv run python eval/run_eval.py --provider claude --out eval/results/claude-opus-5-5.json
uv run python eval/run_eval.py --provider local --out eval/results/arctic-7b-q4.json

# Print the comparison table and write it into the README
uv run python eval/compare.py --readme
```

The free tier allows only a few requests a minute. `--delay` waits that many
seconds between questions, and a question that hits the rate limit waits a
minute and is asked again (up to 3 times), so rate limits don't count as wrong
answers. Claude runs use API credits. Local runs are free but slower.

The model menu in the app reads these result files. After a full run, that model
shows its score, such as "89% on eval", and the most accurate measured model of
each provider is marked with ★. Runs with fewer than 20 questions (`--limit`) are
ignored, and if a model was run several times, the newest file counts. To label
the menu on a server, commit the files in `eval/results/`, or point
`ASKDB_EVAL_RESULTS_DIR` at a folder that has them.

To compare models within one provider, run each with `--model`:

```bash
uv run python eval/run_eval.py --provider claude --model claude-haiku-4-5 --out eval/results/claude-haiku-4-5.json
uv run python eval/run_eval.py --provider claude --model claude-opus-5-5 --out eval/results/claude-opus-5-5.json
``` Commit the files
in `eval/results/` so you can track accuracy over time.

To add questions, append lines to `eval/dataset.jsonl`:

```json
{"id": "short-unique-id", "question": "Plain English question", "gold_sql": "SELECT ...", "ordered": false}
```

Set `"ordered": true` only when row order matters, for example "top 5 ...".
Check the gold query for ties first: if the 5th and 6th rows have the same value,
"top 5" has more than one right answer. The test suite runs every gold query, so
`uv run pytest` catches typos.

### Record the demo GIF

With the backend and frontend running and a working model key, from the
repository root:

```bash
uv run --with playwright playwright install chromium   # first time only
uv run scripts/record_demo.py                           # writes docs/demo.gif
```

It types a question, waits for the answer, opens the self-correction details if
there are any, and asks a follow-up. `--question`, `--follow-up`, `--theme dark`
and `--width` change what's recorded. It needs `ffmpeg`.

---

## 10. Configuration reference

All settings go in `backend/.env`. Every one is optional. Users can add their own
model keys in the app instead of the two key variables.

| Variable | Default | What it does |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | none | Server key for Claude (users can add their own in the app instead) |
| `ASKDB_PROVIDER` | `free` | Default provider: `free`, `claude`, `groq`, `openrouter`, `openai`, `local`, or `auto` (Claude when `ANTHROPIC_API_KEY` is set, otherwise free) |
| `ASKDB_FREE_API_KEY` | none | Server key for the free model (users can add their own in the app instead) |
| `ASKDB_FREE_BASE_URL` | Gemini's OpenAI-compatible URL | Any OpenAI-compatible chat API |
| `ASKDB_FREE_MODEL` | `gemini-flash-latest` | Model name at that API (`uv run askdb --list-models`) |
| `ASKDB_FREE_MODELS` | `[]` | Extra models visitors may pick on the server's free key (the default is always allowed) |
| `ASKDB_FREE_TIMEOUT_S` | `120` | Seconds to wait for a hosted model (free, Groq, OpenRouter, OpenAI) |
| `ASKDB_GROQ_API_KEY` / `_MODEL` / `_MODELS` / `_BASE_URL` | none / `openai/gpt-oss-120b` / `[]` / Groq's API | Groq: server key, default model, models allowed on the server key, endpoint |
| `ASKDB_OPENROUTER_API_KEY` / `_MODEL` / `_MODELS` / `_BASE_URL` | none / `openrouter/auto` / `[]` / OpenRouter's API | OpenRouter, same four settings |
| `ASKDB_OPENAI_API_KEY` / `_MODEL` / `_MODELS` / `_BASE_URL` | none / `gpt-5-mini` / `[]` / OpenAI's API | OpenAI, same four settings |
| `ASKDB_MODEL` | `claude-opus-5-5` | Default Claude model |
| `ASKDB_CLAUDE_MODELS` | Opus 5.5, Sonnet 5.5, Haiku 4.5 | Claude models visitors may pick on the server's key (Fable 5.1 is also available with the user's own key) |
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
| `ASKDB_MAX_UPLOADS` | `20` | Maximum number of uploads per browser |
| `ASKDB_MAX_TOTAL_UPLOADS` | `200` | Maximum number of uploads on the server |
| `ASKDB_EVAL_RESULTS_DIR` | `eval/results` | Eval result files that label the model menu ([section 9](#9-measure-accuracy-evaluation)) |

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
- For PostgreSQL, connect as a dedicated read-only role, never as `postgres`
  or another superuser (see below).

#### A PostgreSQL role for AskDB

AskDB only runs single `SELECT` statements, in read-only transactions with a
statement timeout. That stops writes, but a `SELECT` can still call functions,
and what those functions may do depends on the role. Connected as a superuser,
a validated `SELECT` can read files on the database server
(`pg_read_file('/etc/passwd')`), list its directories (`pg_ls_dir`), read
password hashes from `pg_authid`, and stop other sessions
(`pg_terminate_backend`).

Create a role that can only read the tables you want to ask about. Run this as
an admin, changing the database, schema and password:

```sql
CREATE ROLE askdb_reader LOGIN PASSWORD 'change-me';
GRANT CONNECT ON DATABASE mydb TO askdb_reader;
GRANT USAGE ON SCHEMA public TO askdb_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO askdb_reader;
-- Tables created later in this schema are readable too:
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO askdb_reader;
-- Read-only even if something connects without AskDB's settings:
ALTER ROLE askdb_reader SET default_transaction_read_only = on;
```

Then use `postgresql+psycopg://askdb_reader:change-me@host:5432/mydb`. As this
role the file, directory, password-hash and large-object functions above fail
with "permission denied", and only the granted tables can be read. To hide
sensitive tables or columns from the model, grant `SELECT` on just the ones you
want, or on views. Don't give the role `pg_read_server_files`,
`pg_read_all_data`, `pg_signal_backend`, or membership in an admin role.

The open model is trained on SQLite, so expect it to do better on SQLite
databases than on PostgreSQL.

---

## 11. Troubleshooting

| Problem | Likely cause and fix |
| --- | --- |
| `No API key for the free model` | No key in the browser and none on the server. Click the key button in the top bar and paste a free key from aistudio.google.com/apikey. |
| `The free model API rejected the key` | The key is wrong or was deleted. Create a new one and paste it in the API keys dialog. |
| `Model "…" not found` | That model isn't available to your key. Pick another in the model menu, or run `uv run askdb --list-models --provider <name>` and set `ASKDB_<NAME>_MODEL` to one of them. |
| `… needs your own API key` | The server only lets visitors use the models in `ASKDB_*_MODELS`. Add your own key under **API keys**, or ask the operator to allow the model. |
| `Free-tier rate limit reached` | Free tiers allow only a few requests per minute. Wait a minute and try again. |
| `No Anthropic key` | You picked Claude but haven't added an Anthropic key. Add one in the API keys dialog, or switch back to **Free**. |
| `The Anthropic API rejected the key` | The key is wrong or revoked. Create a new one. |
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
| `This server is full` | The server has `ASKDB_MAX_TOTAL_UPLOADS` uploads. Remove old ones from `backend/data/uploads/` or raise the limit. |
| An upload disappeared | Uploads belong to the browser that made them. Use the same browser, without clearing site data. |
| `needs a header row and at least one data row` | The CSV's first line must be column names, followed by data. |
| `That database no longer exists.` | Someone deleted the upload. Pick another database from the menu. |

Still stuck? Run the backend tests (`uv run pytest`). If they pass, the backend
code is fine and the problem is in configuration or the model connection.
