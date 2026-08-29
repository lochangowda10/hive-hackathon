# Hackathon Disclosure & Judge Q&A — Team Hive

## Origin disclosure (we say this first, before anyone asks)

**SwingLens existed before this hackathon.** The pre-existing codebase is
public at `github.com/hanamaraddi9620adi/swinglens`. This repository was
started fresh from that codebase at kickoff. Everything we build during the
event lands as individual, timestamped commits on top of the initial commit —
**our hackathon diff is `git log` after commit `f9fe9a1`, and it is our
evidence.** We confirmed with the organizers that building on prior work is
permitted *([confirm organizer name + time here before judging])*.

---

## The product we are building toward

**One platform that combines what retail traders currently pay for or stitch
together across three apps:**

1. **Broker-grade charting & portfolio context** (the INDmoney / Groww /
   Zerodha experience) — full chart detail, holdings, watchlists, alerts —
   **without order placement**. We are deliberately not a broker: no buy/sell
   buttons means no conflict of interest. We never profit from your trades.
2. **A strategy engine that investing.com charges for, free** — pivot
   detection, S/R zones, breakouts, entry/stop/target plans, universe
   scanner, and a *published* track record. Their "ideas" are black boxes;
   ours shows every number's derivation and grades itself in public.
3. **Catalyst-aware news** — not a headline dump: a 2-source CONFIRMED gate,
   per-symbol news wired into the chart, and (roadmap) catalyst tagging so a
   user sees *why* a stock is running, not just that it is.

Technical + fundamental + sentiment analysis, one screen, free, accountable.

---

## Judge questions — our answers, rehearsed

### Q1. "One commit — what did you build in 24 hours?"
Disclosure above, in the first ten seconds of the demo, before being asked.
Every hour of event work is a separate commit; the delta is auditable.

### Q2. "Where's the AI?"
Two-layer answer:
1. **We made the LLM auditable.** Most AI-finance apps let the model invent
   numbers — ours physically cannot. The model narrates; deterministic math
   calculates. Every narration block is verified against computed facts, and
   it degrades to templates when the model is offline. Solving *trustworthy*
   AI is harder than prompting, and it's the problem that actually matters
   in finance.
2. **We ship a learned component: calibration.** Our backtest
   (`backend/scripts/backtest.py`) grades every historical setup and produces
   a reliability table — "when the engine scores X, how often did it win?"
   That table *is* the empirical basis for calibrating the confidence score,
   and we publish it instead of hiding it (see Q4 — it's honestly imperfect).

### Q3. "Who pays and why? Chartink/TradingView/Screener are free."
**Nobody free grades its own calls in public.** That is the product:
> "Every free tool gives you 200 indicators and zero accountability. We're
> the only one that publishes whether we were right."
Monetization: verified-setup reports (₹99 UPI pilot during the event),
then B2B licensing to SEBI-registered advisors who need auditable analysis,
then a hosted Pro tier. Free tools stay free because they sell your order
flow or your attention; we sell accountability.

### Q4. "What's your win rate?"
**53.1% over 194 decided setups**, walk-forward 2021–2026, daily bars,
29 large-cap NSE symbols, avg hold 22.6 bars. Expectancy **+0.62R gross,
+0.58R net** of a 0.15% round-trip cost model. Full artifact:
`backend/backtest_results.json` — reproducible with
`python -m scripts.backtest`.
Stated with its weaknesses *before being asked*:
- **Survivorship bias** — the universe is today's large caps, not 2021's.
- **Pivot lag** — swing pivots confirm 3 bars late, in backtest exactly as
  in live trading (we did not "fix" it with future data).
- **Baseline** — 53% at ~1.5:1+ R:R is meaningfully above the ~40%
  breakeven for that R:R; that's why expectancy (+0.6R) is the headline,
  not win rate alone.
- **Calibration gap** — our reliability table shows the heuristic score is
  NOT yet monotonic (60–79 bucket underperformed 40–59). We show this
  publicly. Fixing it with a learned calibrator is on our roadmap — most
  tools would never show you this table.

### Q5. "Are you SEBI registered?"
"We're an analysis and education tool, not an advisory — the engine shows
what the data says with full sourcing; the user makes the call. There is no
order placement and no personalized recommendation. The commercial path is
either Research Analyst registration or B2B licensing to already-registered
advisors." A visible disclaimer ships in the UI (Login + every screen) and
in every API payload's source notes. *(Not legal advice — we're getting a
professional opinion before any commercial launch.)*

### Q6. "How is this different from TradingView?"
**"TradingView shows you the chart. It has no opinion and no record. We take
a position on every setup and publish whether we were right."**

### Q7. "Local-first with a 5GB model — who's the user? And is there a URL?"
Local-first is the **privacy differentiator** (your portfolio never leaves
your machine); hosted is the **product** — same codebase, adapter pattern,
one-command Docker deploy (`DEPLOY.md`, demo mode + cloud LLM fallback
included). Public demo URL: **[fill in at deploy]**.

### Q8. "Show me a user who isn't you."
**[Fill in: N testers from the venue, screenshots, what they broke, what we
changed because of them.]**

### Q9. "yfinance in production?"
It's behind an adapter (`services/market_data.py` is the only file that
imports yfinance). Swapping to a licensed NSE feed (Angel One / Dhan /
bhavcopy) is a config change, not a rewrite — that's why the adapter pattern
exists. Cost line for a licensed feed is in the SaaS plan.

### Q10. "If your engine has a real edge, why aren't you just trading it?"
**"Because the edge isn't the signal — it's the discipline. Retail traders
lose to emotion, not to bad indicators. We sell a process that doesn't
flinch, and a track record that proves it didn't. A 0.6R expectancy only
pays if you take *every* setup — humans can't; software can show them what
that discipline would have earned."**

---

## Backtest quick reference (memorize these)

| Metric | Value |
|---|---|
| Win rate | **53.1%** (103W / 91L, 194 decided) |
| Expectancy | **+0.62R gross / +0.58R net** |
| Sample | 238 setups, 29 NSE large caps, 2021–2026, daily |
| Avg hold | 22.6 bars |
| Pullbacks vs breakouts | 59.6% vs 50.7% win rate |
| Calibration | Not yet monotonic — published, fixable, roadmap |
| Reproduce | `cd backend && python -m scripts.backtest` |
