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
| `src/components/AskApp.tsx` | Page layout, state, history, and calls to the API |
| `src/components/Header.tsx` | Top bar: backend status, source link, theme toggle |
| `src/components/Composer.tsx` | Question box and Claude / open-model switch |
| `src/components/Examples.tsx` | Example question cards |
| `src/components/ResultView.tsx` | Answer summary, chart/table tabs, single-value card, CSV export |
| `src/components/PipelineSteps.tsx` | What each pipeline stage did for this answer |
| `src/components/AttemptsView.tsx` | Self-correction timeline: failed queries and their errors |
| `src/components/SqlCard.tsx` | Highlighted SQL with copy button |
| `src/components/ResultChart.tsx` | Bar/line chart (Recharts) picked by the backend |
| `src/components/ResultTable.tsx` | Result rows |
| `src/components/Sidebar.tsx` | Recent questions and a searchable schema browser |
| `src/components/StatusViews.tsx` | Loading and error states |
| `src/lib/` | API types, number formatting, CSV, SQL highlighting, backend proxy |
| `src/app/api/*/route.ts` | Proxy to the Python API |

Light, dark, and system themes are supported (toggle in the header). Chart
colors come from a colorblind-validated categorical palette, defined as CSS
variables in `src/app/globals.css`.
