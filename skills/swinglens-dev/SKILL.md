---
name: swinglens-dev
description: Development conventions, architecture laws, and agent hygiene for building SwingLens (a local-first swing-trading analysis platform - FastAPI + React + lightweight-charts v5 + Ollama). ALWAYS use this skill when working on SwingLens or any stock/trading platform code in this workspace - including new features, bug fixes, indicators, news, portfolio, chart, AI-chat, or SaaS-migration tasks - even if the user doesn't mention the skill. Also trigger for writing "master prompts", planning phases, or reviewing agent output for this project.
---

# SwingLens Development Skill

You are building SwingLens: a beginner-to-advanced stock research platform
(Indian + US markets) that reproduces how a human analyst annotates a chart.
Local-first (Ollama, SQLite, free data), architected to flip to SaaS.

## The Five Laws (never violate these)

1. **Numbers come from math or data sources — NEVER from an LLM.**
   The LLM only explains computed facts. Any narration pass must be followed
   by verification that every number it used exists in the fact payload.
   Corollary: the LLM NEVER picks or recommends stocks — "which stocks look
   bullish" routes to the deterministic scanner (services/scanner.py), which
   runs the analysis engine across a whole universe and ranks by confidence.
2. **Every data payload carries a `source` block** — provider name, clickable
   URL, fetch timestamp, optional honesty note — and the UI displays it.
3. **Every external system sits behind an adapter/registry seam** (LLM
   adapter, data loaders, indicator registry, broker adapters later) so local
   mode and SaaS mode are the same code with different config.
4. **Honesty over impressiveness.** "No clean setup" is a valid, styled
   output. Curated universes are labeled curated. Dead feeds are named.
   USD commodity futures are never presented as MCX ₹ quotes.
5. **Whole-file rewrites only.** NEVER patch files with sed, partial string
   inserts, or line-number edits. If a file needs changing, regenerate the
   complete file. This single rule prevents the corruption failure class.

## Agent hygiene (learned from real failures in this project)

- Large specs (e.g. a 90-indicator list) are fed **one category per run** —
  monolithic prompts cause decode timeouts and half-written files.
- Never claim work is done without proof: check `/docs` for routes, run
  `pytest -q`, run `npm run build`. A summary is not a verification.
- Every phase ends with: tests green, frontend builds, README updated.
- New dependencies require: what it is, why, cost (prefer free), 1-2
  alternatives — stated to the user before installing.

## Architecture map

```
backend/app/
  config.py            # all settings from .env
  auth.py              # PBKDF2 + JWT
  models.py            # User, TradePlan (self-grading roadmap)
  routers/             # auth, stocks, ai, analysis, indicators, markets, news
  services/
    market_data.py     # yfinance candles + search + source blocks
    markets.py         # curated universes, movers, local_search (name-first)
    analysis_engine.py # pivots→zones→trendlines→setup→plan→confidence
    indicators.py      # registry: 27 indicators w/ education metadata
    news.py            # RSS + 2-source CONFIRMED corroboration gate
    narration.py       # LLM narration + deterministic number verifier
    llm/               # adapter seam: Ollama now, cloud later
frontend/src/
  api.js               # every backend call
  components/          # CandleChart (types+panes+annotations), SetupCard,
                       # AIChat (context-grounded), IndicatorDialog/Chips,
                       # TickerStrip, SymbolNews, StockSearch, SourceFooter
  pages/               # Pulse (news sky), Explore (segments), Workspace, Login
  utils/chartTypes.js  # 10 chart views incl. Heikin Ashi
```

Design system: ink blue-black base (#070b14/#0c1220), brass accent #e8b64c,
bull #22c07a / bear #ef5350, Space Grotesk display, JetBrains Mono for every
price (tabular-nums), rise-in reveals, honest empty states.

## Phase workflow

Phases so far: 1 skeleton → 2 analyst engine → 2.1 chat-to-analyze →
2.5 indicator toolbox → 2.75 markets explore → 3 newsroom+grounded chat →
3.75 market scanner + persistent conversations → 4 portfolio mirror
(tolerant broker import, FIFO analytics, personality engine) →
4.5 showcase (Docker, demo mode, cloud LLM option) → 4.75 alive
(watchlist, price alerts, position sizer, and the self-grading Engine
Track Record — plans graded pessimistically against real candles).
Next: 5 SaaS
(Docker, Postgres, broker APIs, SEBI-aware framing).

Each phase delivery = working code + tests + build proof + updated README +
a **master prompt**: one dense standalone paragraph a fresh agent could
execute, always ending with test requirements and the whole-file rule.

## Commands

```
backend:  venv\Scripts\activate && pytest -q && uvicorn app.main:app --reload --port 8000
frontend: npm install && npm run build && npm run dev
```

## When reviewing another agent's output on this project

Check in order: (1) did it violate a Law, (2) did it sed-patch anything,
(3) do tests pass, (4) does the build pass, (5) does every new payload carry
a source block, (6) did the LLM originate any number anywhere. Reject and
regenerate whole files on any failure.
