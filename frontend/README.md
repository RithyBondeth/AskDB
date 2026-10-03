# AskDB frontend

Next.js (App Router) UI for AskDB. See the [root README](../README.md) for the full setup.

```bash
npm install
cp .env.example .env.local   # points at the Python API, default http://127.0.0.1:8000
npm run dev                  # http://localhost:3000
```

The browser only talks to this app. Route handlers in `src/app/api/` forward
requests to the Python backend, so the backend URL stays server-side and no
CORS setup is needed.

| Path | Purpose |
| --- | --- |
| `src/components/AskApp.tsx` | Conversation state, streaming, follow-up context, share links, shortcuts |
| `src/components/TurnView.tsx` | One question and its answer: live pipeline, result, self-correction, follow-ups |
| `src/components/LivePipeline.tsx` | Generate → Validate → Execute → Present, updated live from the stream |
| `src/components/ResultPanel.tsx` | Chart / Table / SQL tabs, chart type switch, row filter, CSV |
| `src/components/ResultTable.tsx` | Sortable, filterable result table |
| `src/components/ResultChart.tsx` | Bar/line chart (Recharts) |
| `src/components/SqlEditor.tsx` | Highlighted SQL with edit, run (⌘↵), revert, and copy |
| `src/components/AttemptsView.tsx` | Self-correction timeline |
| `src/components/Composer.tsx` | Question box, model switch, stop button |
| `src/components/CommandPalette.tsx` | ⌘K palette: ask, actions, recent, examples |
| `src/components/Sidebar.tsx` | Recent questions and schema browser (click to insert), plus the mobile drawer |
| `src/components/Header.tsx` | Top bar: new chat, ⌘K, status, theme |
| `src/lib/stream.ts` | Client for the streaming and run-SQL endpoints |
| `src/lib/` (other) | Types, theme, examples, formatting, CSV, SQL highlighting, backend proxy |
| `src/app/api/*/route.ts` | Proxy to the Python API (the stream route passes events through unbuffered) |

**Keyboard:** `↵` ask · `⇧↵` new line · `⌘K` / `Ctrl+K` command palette · `/`
focus the question box · `⌘↵` run edited SQL.

Light, dark, and system themes are supported (toggle in the header). Chart
colors come from a colorblind-validated categorical palette, defined as CSS
variables in `src/app/globals.css`.
