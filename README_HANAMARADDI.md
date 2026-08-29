# Hanamaraddi — Backend & Analysis Engine

You own everything from the HTTP boundary downwards: FastAPI routers,
services, the Analyst Engine, data adapters, the LLM adapters, auth, and the
database. Lochan builds the UI against your API and never needs to touch
Python; you never need to touch JSX. **The `/api/*` contract is the border —
if you change a response shape, tell Lochan before merging.**

## Your zone

```
backend/
└── app/
    ├── main.py            App entry, CORS, router registration, SPA serving
    ├── config.py          Every setting comes from .env
    ├── auth.py            PBKDF2 password hashing + JWT sessions
    ├── database.py        SQLAlchemy engine/session
    ├── models.py          User table (extend here for new persisted entities)
    ├── routers/           Thin HTTP layer — parse, call a service, respond
    │   ├── auth_routes.py     signup/login/me
    │   ├── stocks.py          candles + search
    │   ├── analysis.py        the Analyze endpoint
    │   ├── indicators.py      indicator catalog + compute
    │   ├── markets.py         overview/segments (ticker, explore)
    │   ├── news.py            market + per-symbol news
    │   ├── scan.py            universe scanner
    │   ├── portfolio.py       broker-file import, holdings, behavior
    │   ├── ai.py              chat, status, conversations
    │   └── tracking.py        watchlist, alerts, plans, track record
    └── services/          All the brains live here
        ├── analysis_engine.py pivots → zones → trendlines → breakout → plan
        ├── grader.py          self-grades saved plans vs actual price
        ├── indicators.py      27 indicator implementations (pure math)
        ├── market_data.py     yfinance adapter + source blocks
        ├── markets.py         overview/segment universes
        ├── news.py            RSS fetch + 2-source CONFIRMED gate
        ├── portfolio.py       CSV/XLSX sniffing import, FIFO P&L
        ├── scanner.py         batch-runs the engine over universes
        ├── narration.py       4-block verified narration (+ template fallback)
        └── llm/               base / ollama_adapter / cloud_adapter
```

## Your non-negotiables

1. **Numbers come from data or math, never from the AI.** If a value appears
   in a response, it must be traceable to a computation. The LLM narrates;
   it never calculates.
2. **Every payload carries a `source` block** — provider, link, timestamp.
3. **Every external system sits behind an adapter** (yfinance today, NSE /
   broker APIs tomorrow; Ollama today, cloud LLM tomorrow).
4. **Routers stay thin.** Logic goes in `services/` where it's testable.
5. **`pytest -q` stays green.** Engine math changes need a test.

## Run your half

```
cd backend
run via:  ..\run-backend.bat     (or)  venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
tests:    venv\Scripts\python -m pytest -q
docs:     http://127.0.0.1:8000/docs   (auto-generated API reference)
```

## Your independent work streams

Pick any of these without waiting on the frontend — each is self-contained
and testable via `/docs` or pytest:

1. **Backtesting & grading depth** — richer grading windows, per-setup-type
   win rates, expectancy and drawdown stats for the Track Record endpoint.
2. **Scanner intelligence** — new universe definitions, pre-market gap scan,
   volume-breakout scan. Engine ranks, never the LLM.
3. **Data adapters** — a second market-data provider behind the same
   interface as `market_data.py` (failover + "source" honesty).
4. **Broker adapters (Phase 5)** — read-only Zerodha/Upstox import behind an
   adapter, replacing CSV upload for users who connect a broker.
5. **PostgreSQL migration (Phase 5)** — DATABASE_URL already abstracts this;
   prove it with a Postgres docker-compose run.
6. **Performance** — candle/indicator caching layer, batch yfinance loads,
   response compression.

## Definition of done (backend)

- New logic lives in `services/`, covered by a pytest.
- Response includes a `source` block if it wraps external data.
- `pytest -q` passes; `/api/health` returns ok; the frontend still works
  with zero changes unless the API contract was deliberately extended
  (and Lochan was told).
