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
| `src/components/Header.tsx` | Top bar: database picker, new chat, ⌘K, status, theme |
| `src/components/DatabasePicker.tsx` | Switch between the sample and uploaded databases; delete uploads |
| `src/components/UploadDialog.tsx` | Drag-and-drop upload of SQLite or CSV files, with progress |
| `src/components/Doodle.tsx` | Renders an Open Doodles illustration in the theme's ink and accent colors |
| `src/lib/doodles.ts` | The illustrations used (Open Doodles, CC0), as minified SVG paths |
| `src/lib/stream.ts` | Client for the streaming and run-SQL endpoints |
| `src/lib/` (other) | Types, theme, examples, formatting, CSV, SQL highlighting, backend proxy |
| `src/app/api/*/route.ts` | Proxy to the Python API (the stream route passes events through unbuffered) |

**Keyboard:** `↵` ask · `⇧↵` new line · `⌘K` / `Ctrl+K` command palette · `/`
focus the question box · `⌘↵` run edited SQL.

**Design.** A calm, hand-drawn "doodle" look: faint dotted paper, thin ink
lines with softly uneven corners, light offset shadows, pastel suggestion cards,
and a highlighter mark in light mode, and chalk on a blackboard in dark mode.
The interface uses Nunito for readability. The handwritten Caveat appears only
in the logo and the home headline, and SQL uses Geist Mono. The building blocks
(`.card`, `.sketch`, `.btn-ink`, `.btn-paper`, `.note`, `.hl`) and all colors
are in `src/app/globals.css`. Illustrations from [Open Doodles](https://www.opendoodles.com)
(Pablo Stanley, CC0) mark the home, thinking, error, no-rows, and upload states.
Chart colors are a colorblind-validated categorical palette for each theme.
