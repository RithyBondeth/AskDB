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
| `src/components/AskApp.tsx` | Question box, example prompts, result layout |
| `src/components/AttemptsView.tsx` | Failed attempts and the errors fed back to the model |
| `src/components/ResultChart.tsx` | Bar/line chart picked by the backend |
| `src/components/ResultTable.tsx` | Result rows |
| `src/components/SchemaPanel.tsx` | Browsable schema sidebar |
| `src/app/api/*/route.ts` | Proxy to the Python API |
