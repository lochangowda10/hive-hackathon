import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../auth'
import AIChat from '../components/AIChat'
import CandleChart from '../components/CandleChart'
import StockSearch from '../components/StockSearch'
import TickerStrip from '../components/TickerStrip'
import WatchStrip from '../components/WatchStrip'
import AlertBell from '../components/AlertBell'
import { api } from '../api'
import Explore from './Explore'
import Pulse from './Pulse'
import Portfolio from './Portfolio'
import Research from './Research'
import Discovery from './Discovery'
import SymbolNews from '../components/SymbolNews'

const QUICK_PICKS = ['RELIANCE.NS', 'TATAMOTORS.NS', 'SUZLON.NS', 'AAPL', 'NVDA']

export default function Workspace() {
  const { user, logout } = useAuth()
  const [view, setView] = useState('pulse')
  const [symbol, setSymbol] = useState('RELIANCE.NS')
  const [analyzeReq, setAnalyzeReq] = useState(0)
  const [latestAnalysis, setLatestAnalysis] = useState(null)
  const [newsTitles, setNewsTitles] = useState([])
  const [portfolioCtx, setPortfolioCtx] = useState(null)
  const [watchlist, setWatchlist] = useState([])

  const loadWatchlist = () => api.watchlist().then((d) => setWatchlist(d.items || [])).catch(() => {})
  // Wrap in a body so the effect returns undefined, not the Promise from
  // loadWatchlist - React would try to call that Promise as the cleanup
  // function on unmount ("destroy is not a function").
  useEffect(() => { loadWatchlist() }, [])

  const toggleWatch = async (sym) => {
    try { await api.toggleWatch(sym, sym); loadWatchlist() } catch { /* offline */ }
  }

  // "/" focuses search from anywhere
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) {
        e.preventDefault()
        document.querySelector('#global-search input')?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // What the AI is allowed to see and cite - nothing more.
  const chatContext = useMemo(() => ({
    symbol,
    analysis: latestAnalysis ? {
      setup: latestAnalysis.setup,
      indicators: latestAnalysis.indicators,
      narration: latestAnalysis.narration,
    } : null,
    news_titles: newsTitles.slice(0, 10).map((n) => ({
      title: n.title, source: n.source_name, confirmed: n.confirmed,
    })),
    portfolio: portfolioCtx,
  }), [symbol, latestAnalysis, newsTitles, portfolioCtx])

  const openSymbol = (sym) => {
    setSymbol(sym)
    setView('chart')
  }

  // Chat-resolved "analyse <stock>": switch chart + fire the pipeline.
  const requestAnalyze = (sym) => {
    setSymbol(sym)
    setView('chart')
    setAnalyzeReq((n) => n + 1)
  }

  const tab = (id, label) => (
    <button
      onClick={() => setView(id)}
      className={`text-sm px-3 py-1.5 rounded-lg transition-colors ${
        view === id ? 'text-brass-400 bg-brass-400/10' : 'text-mist-400 hover:text-mist-50'
      }`}
    >
      {label}
    </button>
  )

  return (
    <div className="min-h-full flex flex-col">
      <header className="sticky top-0 z-20 bg-ink-950/85 backdrop-blur border-b border-ink-700">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-3 flex items-center gap-4">
          <div className="flex items-center gap-2.5 shrink-0">
            <span className="w-8 h-8 rounded-lg bg-brass-400 grid place-items-center font-[family-name:var(--font-display)] font-bold text-ink-950">S</span>
            <span className="font-[family-name:var(--font-display)] text-mist-50 font-semibold tracking-tight hidden sm:block">SwingLens</span>
          </div>

          <nav className="flex items-center gap-1 shrink-0">
            {tab('pulse', 'Pulse')}
            {tab('explore', 'Explore')}
            {tab('chart', 'Chart')}
            {tab('research', 'Research')}
            {tab('discover', 'Discover')}
            {tab('portfolio', 'Portfolio')}
          </nav>

          <div id="global-search" className="flex-1 flex justify-center">
            <StockSearch onSelect={openSymbol} />
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <AlertBell onOpenSymbol={openSymbol} />
            <span className="text-sm text-mist-400 hidden md:block">{user?.username}</span>
            <button
              onClick={logout}
              className="text-xs text-mist-400 hover:text-mist-50 border border-ink-600 hover:border-ink-500 rounded-lg px-3 py-1.5 transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>
        <TickerStrip onOpenSymbol={openSymbol} />
      </header>

      <main className="flex-1 max-w-[1400px] w-full mx-auto px-4 sm:px-6 py-5">
        {view === 'pulse' ? (
          <Pulse onOpenSymbol={openSymbol} />
        ) : view === 'explore' ? (
          <Explore onOpenSymbol={openSymbol} />
        ) : view === 'research' ? (
          <Research symbol={symbol} />
        ) : view === 'discover' ? (
          <Discovery onOpenSymbol={(sym) => { setSymbol(sym); setView('research') }} />
        ) : view === 'portfolio' ? (
          <Portfolio onOpenSymbol={openSymbol} onPortfolio={setPortfolioCtx} />
        ) : (
          <>
            <WatchStrip items={watchlist} symbol={symbol} fallback={QUICK_PICKS}
                        onOpen={setSymbol} onRemove={toggleWatch} />

            <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-5 items-start">
              <CandleChart symbol={symbol} analyzeSignal={analyzeReq} onAnalysis={setLatestAnalysis}
                           watched={watchlist.some((i) => i.symbol === symbol)}
                           onToggleWatch={toggleWatch} />
              <div className="flex flex-col gap-5">
                <AIChat onAnalyze={requestAnalyze} onOpenSymbol={openSymbol} context={chatContext} />
                <SymbolNews symbol={symbol} onLoaded={setNewsTitles} />
              </div>
            </div>
          </>
        )}

        <p className="mt-6 text-[11px] text-mist-400/70 leading-relaxed max-w-3xl">
          SwingLens is a research and education tool — not investment advice, and not a
          SEBI-registered advisory. The engine shows what the data says with full sourcing;
          you make the call. It never executes trades. Verify anything important at the
          linked sources before acting.
        </p>
      </main>
    </div>
  )
}
