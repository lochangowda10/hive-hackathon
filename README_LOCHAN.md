# Lochan — Frontend & Product Experience

You own everything the user sees and touches: the React app, charts,
dashboards, dialogs, design system, and the overall product feel. Hanamaraddi
owns the API behind `/api/*` — you build against it and never need to touch
Python. **If you need a new field or endpoint, ask for it (or mock it in
`api.js` first) — don't change the backend yourself.**

## Your zone

```
frontend/
├── index.html             App shell + fonts + title
├── vite.config.js         Dev server + /api proxy to :8000
└── src/
    ├── api.js             EVERY backend call goes through here — the contract
    ├── auth.jsx           Auth context (login state, token)
    ├── ErrorBoundary.jsx  Never let the app white-screen
    ├── App.jsx / main.jsx Routing + bootstrap
    ├── pages/
    │   ├── Login.jsx          Brand panel + auth forms
    │   ├── Workspace.jsx      Main shell: chart + chat + news
    │   ├── Pulse.jsx          Market overview, headline sky, Track Record
    │   ├── Explore.jsx        Market segments + sparklines
    │   └── Portfolio.jsx      Holdings dashboard + import flow
    ├── components/
    │   ├── CandleChart.jsx    Chart engine wrapper (lightweight-charts)
    │   ├── IndicatorDialog.jsx  27-indicator picker (ƒx button)
    │   ├── IndicatorChips.jsx   Active indicator chips + params
    │   ├── SetupCard.jsx        Entry/stop/target plan + position size calc
    │   ├── AIChat.jsx           Context-grounded chat UI
    │   ├── StockSearch.jsx      Name-first typo-tolerant search
    │   ├── TickerStrip.jsx      Clickable live ticker
    │   ├── WatchStrip.jsx       Watchlist strip
    │   ├── AlertBell.jsx        Price alerts
    │   ├── SymbolNews.jsx       Per-symbol news panel
    │   ├── TrackRecord.jsx      Engine win-rate display
    │   └── SourceFooter.jsx     The honesty footer — keep it everywhere
    └── utils/chartTypes.js  10 chart-type definitions + transforms
```

## Your non-negotiables

1. **`useEffect` returns a cleanup function or NOTHING.** Returning a Promise
   crashes React on unmount ("destroy is not a function"). Wrap async work:
   `useEffect(() => { load() }, [])`, never `useEffect(load, [])` when
   `load` returns a promise.
2. **All API calls go through `src/api.js`** — never raw `fetch` scattered
   in components (the one existing exception is the health check in Login).
3. **Show the `source` block** (`SourceFooter`) wherever external data is
   displayed. Honesty is the brand.
4. **Never white-screen** — new screens get loading, empty, and error states;
   risky sections sit inside `ErrorBoundary`.
5. **`npm run build` stays green** before you push.

## Run your half

```
cd frontend
run via:  ..\run-frontend.bat     (or)  npm run dev
build:    npm run build
app:      http://localhost:5173   (proxies /api to :8000 automatically)
```

## Your independent work streams

Pick any of these without waiting on backend changes — each is pure frontend:

1. **Design system polish** — consistent spacing/typography scale, dark-theme
   contrast audit, keyboard navigation, mobile responsiveness pass.
2. **Chart UX** — drawing tools (user trendlines/notes), screenshot/share a
   setup card, compare-two-symbols view.
3. **Onboarding** — first-run tour, demo-mode landing, empty-state art and
   copy that teaches the product.
4. **Pulse 2.0** — better headline sky, sector heat tiles, track-record
   visualizations (equity curve of engine calls).
5. **Accessibility & performance** — aria labels, focus states, bundle
   splitting (`React.lazy` per page), lighthouse score.
6. **PWA (Phase 5)** — installable app, offline shell, push alerts when the
   backend alert engine fires.

## Definition of done (frontend)

- Works on 1280px laptop and 390px phone.
- Loading / empty / error states exist for every async panel.
- `npm run build` passes; no new console errors; no `useEffect` returns a
  non-function.
- Any new API need is listed in the PR description so Hanamaraddi sees it.
