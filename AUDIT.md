# SwingLens — Technical Audit & Transformation Plan (deliverable A–R)

> Method: full-repo audit of the working application. Rule enforced
> throughout: **zero dead buttons, zero fake pages, zero invented numbers.**
> Anything not backed by a working pipeline is listed here as "not built"
> and never appears in the UI as a live nav item.

## A. Existing project audit

### Works (verified, tests green — 39 passing)
| Area | Evidence |
|---|---|
| Auth (PBKDF2 + JWT, multi-user) | `auth.py`, tests |
| Candle engine + 10 chart types + 27 indicators | `CandleChart.jsx`, `indicators.py` |
| Analyst Engine (pivots/zones/breakout/plan/confidence) | `analysis_engine.py`, 23 engine tests |
| Self-grading Track Record | `grader.py`, public on Pulse |
| Walk-forward backtest (53.1% / +0.58R) | `scripts/backtest.py`, committed artifact |
| Research engine (5 scores, multi-model fair value, value traps, verdict, thesis) | `research_engine.py`, 8 tests |
| Discovery lists (6 ranked tables) | `routers/research.py`, live-tested 27/30 large caps |
| News with 2-source CONFIRMED gate | `news.py` |
| Portfolio import (CSV/XLSX sniffing, FIFO P&L, Mirror) | `portfolio.py` |
| Watchlist, price alerts, position-size calc | `tracking.py` |
| AI chat (Ollama/cloud adapter, verified narration) | `llm/*`, `narration.py` |
| Pulse / Explore dashboards, ticker, global search | pages/components |
| Error boundaries, backend-down banner, disclaimers | `ErrorBoundary.jsx`, pages |

### Partially implemented
- **Screener**: Discovery lists exist but no custom user filters / NL query.
- **Alerts**: price-only; no fair-value/thesis/news rules.
- **What Changed / Thesis Monitor**: data available, feature not built. **→ flagship, built in this phase.**
- **Search**: stocks/ETF/indices/crypto yes; news/events search no.

### Not built (honest list — will NOT be faked)
Economic calendar, earnings calendar, pre-market/after-hours, insider/
institutional activity, broker directory, academy, financial calculators,
multi-watchlists, compare view, heatmap/matrices, light theme.
(Each needs either a data provider we don't have or a Phase-2 slot.)

### Broken / fixed this week
- `useEffect` Promise-cleanup crash (fixed).
- yfinance camelCase row names broke fundamentals (fixed with normalized matching).
- uvicorn log-redirect crash on Windows (fixed launcher).

## B. Current architecture
FastAPI + SQLite + adapters (market data / fundamentals / news / LLM) +
React/Vite SPA with view-state navigation. Tests: pytest (engine, research,
auth flows). Deploy: Dockerfile + single-origin serving.

## C. Problems found (prioritized)
1. View-state navigation, no URLs → can't deep-link a stock. *Phase 2: real router.*
2. Research/discovery first-load latency (~80s per universe) → needs background precompute. *Accepted with cache + loading copy for now; Phase 5: worker.*
3. No thesis persistence → the differentiator is missing. ***Fixed this phase.***
4. No command palette / keyboard-first nav. ***Fixed this phase.***
5. SQLite + in-process caches won't scale. Phase 5 (Postgres/Redis).

## D. Proposed architecture (target, no rebuild)
Keep adapters; add: `theses` table + `thesis_monitor` service (snapshot →
recompute → diff → health), `what_changed` diff endpoint, background
precompute job (Phase 5), React Router (Phase 2), provider interfaces for
calendar/insider data (Phase 3, marked DEMO until licensed).

## E. Navigation tree (implemented = ✓, else hidden until real)
```
Pulse ✓ | Explore ✓ | Chart ✓ | Research ✓ | Discover ✓ | Portfolio ✓ | Thesis ✓ (new)
⌘K Command palette ✓ (new): search stock, run analysis, open any module,
    find undervalued, thesis monitor — real actions only
Hidden until backed by data: Economic Calendar, Earnings, Brokers,
Academy, Pre/After-market, Insider activity.
```

## F. Route map
Current: SPA views. New API routes this phase:
`POST/GET /api/thesis`, `GET /api/thesis/{id}/health`, `GET /api/research/{symbol}/changes`.

## G. Design system (as-built, keep + extend)
Ink/brass/mist palette, JetBrains Mono numerals, score-badge language
(BAND_STYLE maps), section cards, rise-in micro-motion. New components this
phase: `ThesisCard`, `CommandPalette`, `WhatChangedPanel` — reusing the
badge/table primitives, no new visual dialect.

## H. Component architecture
Pages: +`Thesis.jsx`. Components: +`CommandPalette.jsx`, `WhatChangedPanel.jsx`.
Research page gains Save Thesis CTA + what-changed panel. Workspace hosts
palette + thesis view. No duplication of api.js logic.

## I. Database
New table `theses`: id, user_id, symbol, name, snapshot JSON (scores, fair
value, factors), note, created_at, last_checked_at. SQLite now; same model
valid on Postgres.

## J. API requirements (this phase)
See F. All carry `source`/timestamps; health diff is deterministic math.

## K. Chart architecture
Unchanged (lightweight-charts + overlay). Fair-value line overlay on chart:
Phase 2 quick win, data already in research payload.

## L. Portfolio architecture
Unchanged (import + FIFO + Mirror). Portfolio-vs-fundamentals analytics:
Phase 3, reuses research engine per holding.

## M. AI architecture
Unchanged: models never originate numbers; narration verified. Thesis
health wording uses template-from-facts (LLM optional).

## N. Thesis architecture (flagship — built this phase)
```
save:    research_report → snapshot {scores, fv, upside, factors[], verdict}
monitor: recompute report → per-factor still-true? → score drift
health:  100 − 8·(weakened positives) − 5·(new negatives) − |ΔAI score|
         capped 0-100, every deduction listed (explainable, §45)
changes: human-readable diff lines ("Fair value ₹766 → ₹820 (+7%)",
         "New risk: margins compressing", "Verdict WATCH → ACCUMULATE")
```

## O. Memory architecture (Phase 2 honest slice)
localStorage preferences (horizon, default universe) now; server-side
memory with view/edit/delete in Phase 5.

## P. Testing strategy
This phase: thesis health unit tests (synthetic snapshots), save/list API
test, full pytest green, vite build green. Existing: 39 tests.

## Q. Performance strategy
Report cache 1h, discovery cache 30min, thesis health reuses report cache
(re-check is one recompute, not a full refetch when fresh). Tables stay
server-limited (universe ≤ 30). Virtualization: when universes exceed ~200.

## R. Implementation phases (event-scoped)
1. ✅ Audit doc → 2. ✅ Thesis engine+monitor+what-changed backend+tests →
3. ✅ Thesis UI + palette → 4. Commit/push continuously →
Next: real router + deep links, fair-value chart overlay, precompute worker,
NL screener, deploy.
