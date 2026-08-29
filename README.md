# SwingLens — by Team Hive

> **See the setup. Trust the math. Swing trade with clarity.**

SwingLens is a local-first stock analysis platform that turns raw market data
into **explainable swing-trading setups**. Press **Analyze** on any chart and
the engine detects swing pivots, draws support/resistance zones and trendlines
ON the chart, marks the breakout, computes an entry/stop/target plan with an
explainable confidence score, and narrates it in four short verified blocks —
**every number comes from math, never from the AI.** Every setup is saved and
self-graded against what price actually did, so the engine's public track
record is always honest.

**Team repo:** https://github.com/lochangowda10/hive-hackathon

---

## The real-world problem

Retail swing traders in India (and everywhere) face a rigged toolkit:

- **Professional terminals** (Bloomberg, Refinitiv, even ChartIQ-based tools)
  cost more per month than most retail accounts make.
- **Free tools** give you a chart and 200 indicators — but zero opinion,
  zero plan, and zero accountability. The trader still does all analysis
  by hand, emotionally, inconsistently.
- **"AI stock picker" apps** hallucinate numbers, never show their source,
  and never admit when they were wrong. There is no track record.

Result: retail traders either overpay, under-analyze, or get misled —
and nobody in the chain is accountable for a single call.

## Our answer

| Principle | How SwingLens enforces it |
|---|---|
| **Numbers come from data or math, never from the AI** | The engine computes pivots, zones, breakouts, entry/stop/target and confidence in deterministic Python. The LLM only *narrates* the computed facts — and works offline via Ollama, or falls back to templates. |
| **Every payload carries a `source` block** | Provider, link, timestamp — shown in the UI next to every chart, headline, and plan. |
| **Accountability by default** | Every Analyze plan is saved and self-graded against what price actually did (pessimistic same-candle rule). Win rate is public on the Pulse page. |
| **Local-first, privacy-first** | Your portfolio, watchlist and chats live in a local SQLite file. Nothing leaves your machine unless you deploy it. |
| **Every external system sits behind an adapter** | LLM, market data, (later) brokers — so local mode and SaaS mode are the same code. |

## What's built (working today)

- **Analyst Engine** — pivot detection, S/R zones, trendlines, breakout
  marking, entry/stop/target plans, explainable confidence scoring.
- **Pro charting** — 10 chart types (Heikin Ashi, Hollow candles, Bars,
  Baseline, Area, Step…) + **27 configurable indicators** across
  Trend / Momentum / Volatility / Volume / Levels with plain-language
  "how to read" notes. Settings persist across sessions.
- **Newsroom** — real RSS headlines with a 2-source CONFIRMED gate, Pulse
  dashboard with drifting headline sky, per-symbol news, typo-tolerant search.
- **Portfolio Mirror** — tolerant broker-file import (CSV/XLSX, header
  sniffing, tradebook vs holdings auto-detect), live-priced holdings, FIFO
  realized P&L, Trader Mirror personality with explainable traits.
- **Alive layer** — per-user watchlist, price alerts (checked every 5 min),
  position-size calculator, **Engine Track Record** (self-grading, public).
- **Scanner + AI chat** — engine scans whole universes and ranks setups
  (the LLM never picks stocks); persistent, context-grounded conversations.

## The scalability path (local → product)

```
Today (hackathon)                Next                              SaaS
───────────────────────────────  ────────────────────────────────  ──────────────────────────────
SQLite, single machine           PostgreSQL, Docker (DONE)         Multi-tenant hosted product
yfinance adapter                 NSE/broker API adapters           Real-time websockets, paid data
Ollama local LLM                 Cloud LLM adapter (DONE, Groq)    Fine-tuned narration models
Single-user auth works           Multi-user from day one (DONE)    Teams, shared workspaces
Engine track record per user     Public leaderboards               Verified strategy marketplace
```

Everything the SaaS phase needs is already behind an adapter — scaling is
deployment work, not rewrites. See `DEPLOY.md` for the one-command Docker run
and free hosting path (Render / HF Spaces).

---

## Team Hive — who owns what

We split the project by **layer** so both of us can work independently
without merge conflicts. The contract between the two halves is the
REST API (`/api/*`) — if the API shape changes, we talk first.

| Member | Role | Role file |
|---|---|---|
| **Hanamaraddi** | Backend & Analysis Engine | [README_HANAMARADDI.md](README_HANAMARADDI.md) |
| **Lochan** | Frontend & Product Experience | [README_LOCHAN.md](README_LOCHAN.md) |

**Shared ground rules**
1. Numbers come from data or math, never from the AI.
2. Every payload carries a `source` block.
3. Every external system sits behind an adapter.
4. Work on feature branches: `feat/backend-...` and `feat/frontend-...`.
   Merge to `main` via PR so the other person can eyeball it.
5. Backend changes must keep `pytest -q` green. Frontend changes must keep
   `npm run build` green.

---

## Prerequisites (install once)

| Tool | Where | Notes |
|---|---|---|
| Python 3.11+ | python.org | Tick **"Add Python to PATH"** in the installer |
| Node.js 20 LTS | nodejs.org | Includes npm |
| Ollama | ollama.com | Optional — narration falls back to templates without it |

After installing Ollama: `ollama pull qwen2.5:7b-instruct` (one-time, ~5 GB).

## Run it

**Easy mode (Windows):** double-click `run-backend.bat`, then
`run-frontend.bat`. Done.

**Manual mode:**

```
# Terminal 1 — Backend
cd backend
python -m venv venv            # first time only
venv\Scripts\activate          # first time only
pip install -r requirements.txt  # first time only
copy .env.example .env         # first time only
venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm install                    # first time only
npm run dev
```

Open **http://localhost:5173**, create an account, and search any stock.

Run the engine tests any time: `cd backend && venv\Scripts\python -m pytest -q`.

## Project layout

```
swinglens/
├── backend/                 FastAPI + SQLite          ← Hanamaraddi's zone
│   └── app/
│       ├── main.py          App entry, CORS, routers
│       ├── config.py        All settings from .env
│       ├── auth.py          PBKDF2 passwords + JWT sessions
│       ├── routers/         /api/auth, /api/stocks, /api/analysis, ...
│       └── services/        analysis_engine, indicators, markets, news,
│                            portfolio, scanner, narration, llm/
├── frontend/                React + Vite + Tailwind v4 ← Lochan's zone
│   └── src/
│       ├── pages/           Login, Workspace, Pulse, Explore, Portfolio
│       └── components/      CandleChart, AIChat, IndicatorDialog, ...
├── sample_data/             Demo broker files for import testing
├── DEPLOY.md                Docker + free hosting guide
└── run-backend.bat / run-frontend.bat   one-click launchers
```

## Troubleshooting

**"destroy is not a function" crash** — fixed: a `useEffect` in Workspace was
returning a Promise as its cleanup. Effects must return a function or nothing.

**PowerShell refuses to activate the venv** — use `run-backend.bat` instead,
or run once: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

**AI panel shows "Ollama isn't ready"** — make sure the Ollama app is running
and the model is pulled: `ollama pull qwen2.5:7b-instruct`. Without it,
narration uses deterministic templates — Analyze still works.

**A stock shows "No data found"** — Indian stocks need the exchange suffix:
`RELIANCE.NS` (NSE) or `RELIANCE.BO` (BSE).

**15m / 1H ranges greyed out** — data-provider limit (Yahoo keeps ~60 days of
15-minute bars). Daily and weekly go back decades.

**Port already in use** — change `--port 8000` (backend) or `port: 5173` in
`frontend/vite.config.js` (and the proxy target in the same file).

## Roadmap

- **Phase 2 — Analyst Engine**: DONE
- **Phase 2.5 — Pro toolbox** (chart types + 27 indicators): DONE
- **Phase 3 — Newsroom**: DONE
- **Phase 4 — Mirror (portfolio)**: DONE
- **Phase 4.75 — Alive** (watchlist, alerts, track record): DONE
- **Phase 5 — SaaS**: PostgreSQL, broker API adapters, real-time feeds,
  public track-record leaderboards, hosted launch.
