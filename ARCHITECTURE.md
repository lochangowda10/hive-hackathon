# SwingLens Research Terminal — Architecture (deliverable A–M)

> Scope decision: we extend the existing SwingLens codebase (FastAPI + React,
> adapter pattern already enforced) instead of starting a new monorepo.
> Everything §1–§48 of the spec maps onto the current architecture; the
> monorepo split from §42 becomes the Phase-5 packaging step. This document
> is the contract the implementation follows.

## A. System architecture

```
                        ┌──────────────────────────────┐
                        │  React frontend (Vite)       │
                        │  Research page / Discovery    │
                        └──────────────┬───────────────┘
                                       │ /api/research/*
┌──────────────────────────────────────▼───────────────────────────────┐
│  FastAPI backend                                                      │
│                                                                       │
│  routers/research.py  (thin HTTP layer)                               │
│        │                                                              │
│  services/research_engine.py   ← scores, thesis, verdict (PURE MATH)  │
│        │          │              valuation/fair-value (PURE MATH)     │
│        │          │                                                   │
│  services/fundamentals.py    services/analysis_engine.py (existing)   │
│  FundamentalDataProvider     technical score/pivots/zones             │
│        │                                                              │
│  services/market_data.py     services/news.py (existing)              │
│  MarketDataProvider (yf)     NewsProvider + CONFIRMED gate            │
│        │                                                              │
│  services/llm/* (existing) — narration/thesis wording ONLY            │
└───────────────────────────────────────────────────────────────────────┘
     RAW DATA → VALIDATION → FEATURES → QUANT MODELS → SCORES
     → AI REASONING (wording) → EXPLANATION        (§27 pipeline)
```

**Non-negotiable rules preserved:** AI never invents numbers (§48); every
payload carries a `source` block; every external system sits behind an
adapter (§26); missing data → `"insufficient_data"`, never a guess.

## B. Technology choices

| Spec wants | We use | Why |
|---|---|---|
| React/TS/Next | React + Vite (existing) | Shipping > re-platforming; Next.js is Phase-5 |
| FastAPI | FastAPI (existing) | Already the backend |
| Pandas/NumPy/sklearn | Pandas/NumPy present; sklearn Phase 4 (calibrator) | No fake complexity (§49) |
| PostgreSQL | SQLite now, DATABASE_URL switch later | Already abstracted |
| Redis/Celery | In-process TTL cache now; Redis in Phase 5 | Same reason |
| Charting | lightweight-charts (existing) | Fast, already integrated |

## C. Database schema (new entities, SQLAlchemy)

Existing: `users`, `watchlist`, `alerts`, `plans`, chat tables.
New (added as used, all with `fetched_at` + `source` columns — §25):

```
fundamentals_cache  (symbol PK, payload JSON, fetched_at)
scores_cache        (symbol PK, engine_version, payload JSON, computed_at)
research_reports    (id, user_id, symbol, payload JSON, created_at)
```

Raw statements are NOT normalized into row-per-line-item yet — cached as
provider JSON with timestamps. Normalization is Phase 5 when a second
provider lands; premature normalization is fake complexity.

## D. API architecture (new)

```
GET /api/research/{symbol}            full research payload (scores, fair
                                      value, thesis, verdict, sources)
GET /api/research/discovery/{list}    most_undervalued | most_overvalued |
                                      quality | growth | value |
                                      momentum | cash_flow | value_traps
GET /api/research/{symbol}/financials raw statements (annual, labeled)
```

All responses: `{ data, source: {provider, url, fetched_at, period},
data_quality, engine_version }`.

## E. Scoring formulas (0–100, fully explainable)

Each score returns `{score, band, factors: [{name, value, points, max}]}`.

- **Financial Health** — interest coverage 15, net-debt/EBITDA 15,
  current ratio 10, ROE 10, ROCE 10, PAT margin 10, EBITDA margin 10,
  FCF positivity 10, deleveraging trend 10. Bands: 0-20 Very Weak …
  90-100 Excellent (§4 bands).
- **Cash Flow** — OCF/PAT 20, FCF margin 20, FCF growth 20, positive-FCF
  consistency 20, capex intensity 20. Mismatch (PAT↑ & OCF↓) flags
  `aggressive_accounting` warning.
- **Growth** — revenue CAGR-3Y 30, PAT CAGR-3Y 30, EPS CAGR 20,
  acceleration bonus 20 (latest-year growth > CAGR → "GROWTH ACCELERATION").
- **Profitability** — gross/EBITDA/PAT margins, ROE, ROCE, plus 3Y trends
  (expansion vs compression).
- **Valuation** — derived from blended upside with a hard value-trap
  penalty (§45/46): cheap AND deteriorating = penalized, not rewarded.
- **Technical** — existing analysis-engine confidence + setup state.
- **Risk** (inverse-scored) — leverage, price volatility, margin of
  safety, earnings variability → Low/Moderate/High/Very High.

**AI Score** = fundamentals .25 + valuation .20 + growth .15 + cash flow
.10 + technical .10 + catalysts .10 + quality .05 + (100−risk) .05,
with `positive_factors`, `negative_factors`, `confidence`, `data_freshness`,
`key_assumptions` attached (§9). Verdict bands → STRONG BUY … STRONG SELL,
derived only from score+risk (§35).

## F. Fair-value methodology (multi-model, sector-aware)

Models (each returns per-share value or `None` when data is insufficient):

| Model | Core formula |
|---|---|
| Earnings multiple | fair_PE × forward_EPS; fair_PE = min(hist_avg_PE, industry_PE, 40) |
| PEG | fair_PE = clamp(growth_pct, 5, 40); value = fair_PE × EPS |
| DCF (5Y) | Σ FCF·(1+g)^t / (1+r)^t + TV; r=12%, terminal g=3% |
| FCF yield | FCF_per_share / required_yield(8%) |
| EV/EBITDA | sector_EV_EBITDA × EBITDA − net_debt, ÷ shares |
| P/B–ROE (banks/financials) | BVPS × (ROE−g)/(COE−g), COE=13%, g=5% |

Blending: sector-aware weights — **financials** {pb_roe .40, earnings .30,
peg .15, dcf .15}; **default** {dcf .30, earnings .20, ev_ebitda .15,
fcf_yield .15, comparables .10, peg .10}. Only models with data are blended;
weights renormalize. Scenarios: bear = models − dispersion haircut with
g×0.5 / r+1%; bull = g×1.25 (cap 20%) / r−1%. **Confidence** (§10) =
f(model count, inter-model dispersion, earnings stability, data quality).

## G. AI architecture

LLM (Ollama/cloud adapter, existing) receives the computed payload and may
only *word* the thesis blocks; output is verified against the numbers
(existing narration verification). No LLM → deterministic template thesis.
No number originates in the model, ever.

## H. Frontend pages

New: **Research** page (header, AI score dial, fair-value band
bear→bull vs price, score badges grid, WHY BUY / WHY NOT, statements
summary, valuation history) and **Discovery** page (sortable/filterable
score table per §2 columns subset + list tabs). Existing chart gains a
"Fair value" price line overlay.

## I. Backend folder additions

```
app/services/fundamentals.py       FundamentalDataProvider + cache
app/services/research_engine.py    scores + fair value + thesis + verdict
app/routers/research.py            /api/research/*
backend/scripts/backtest.py        (existing, extended Phase 4)
backend/tests/test_research.py     synthetic-data unit tests
```

## J. MVP roadmap (mapped to spec §43)

- **Now (hackathon):** fundamentals adapter, 5 scores, fair-value engine,
  AI score + verdict + thesis, `/api/research/*`, Research page, Discovery
  table (large+mid universe), value-trap detection, tests.
- **Phase 2:** news-catalyst scoring wired in, fair-value alerts, screener
  NL→filters.
- **Phase 3:** portfolio analytics vs fundamentals, insider/institutional
  (needs licensed data — adapter ready), scenario EV (§29 — formula done,
  probabilities from calibrator).
- **Phase 4:** backtest scores vs NIFTY (framework exists), learned
  calibration, prediction intervals.
- Explicitly stated in UI until Phase 4 lands: **"Scores are computed from
  fundamentals and price math; predictive accuracy is under backtest
  validation — see Track Record."** (§36/§48 honesty.)

## K. External data sources

| Category | Now | Later (adapter swap) |
|---|---|---|
| Prices/candles | Yahoo via `market_data.py` | Angel One / Dhan / bhavcopy |
| Fundamentals/statements | Yahoo via `fundamentals.py` | Screener/Tijori/licensed feed |
| News | RSS via `news.py` | Paid newswire |
| Macro/institutional/insider | not yet | NSE filings, Trendlyne-style feed |

## L. Example data flow (RELIANCE.NS research)

1. `GET /api/research/RELIANCE.NS` → router checks `scores_cache`
   (TTL 6h) → miss → `fundamentals.get_fundamentals("RELIANCE.NS")`
   (statements + info, cached 12h) → validation (missing fields logged,
   data_quality computed) → `research_engine.score_company(...)` →
   sub-scores + fair-value blend + thesis → payload cached → response with
   `source` blocks and `data_quality`.
2. Frontend Research page renders badges, fair-value band, thesis.
3. LLM narration (optional) re-words `positive_factors`/`negative_factors`;
   verifier rejects any number not in the payload.

## M. Worked example (synthetic ABC Ltd)

Inputs: price 120, EPS 8, BVPS 40, hist_avg_PE 18, industry_PE 22,
rev CAGR-3Y 15%, FCF/share 9, ROE 18%, net debt/EBITDA 0.8, sector=default.

- earnings_multiple: min(18,22,40)=18 × 8×1.15 = **165.6**
- peg: clamp(15,5,40)=15 × 8 = **120**
- dcf (g=15% cap, r=12%, tg=3%, 5y on FCF 9): ≈ **158**
- fcf_yield: 9/0.08 = **112.5**
- ev_ebitda: (needs EBITDA; say value **140**)
- blend default weights (dcf .30, earnings .20, ev .15, fcf .15, peg .10,
  comparables absent→renormalized): ≈ 0.30·158 + 0.20·165.6 + 0.15·140 +
  0.15·112.5 + 0.10·120 ≈ **147.9 base** → upside ≈ **+23%**
- bear (g×0.5, r+1%): ≈ **118** ; bull (g×1.25, r−1%): ≈ **186**
- confidence: 5 models, low dispersion, stable earnings → ~75%
```
