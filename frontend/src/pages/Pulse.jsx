import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import TrackRecord from '../components/TrackRecord'

const age = (iso) => {
  if (!iso) return ''
  const mins = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 60000))
  if (mins < 60) return `${mins}m ago`
  const h = Math.round(mins / 60)
  return h < 24 ? `${h}h ago` : `${Math.round(h / 24)}d ago`
}

function Badge({ confirmed, sources }) {
  return confirmed ? (
    <span title={`Corroborated by: ${sources.join(', ')}`}
          className="text-[9px] uppercase tracking-wider rounded px-1.5 py-0.5 border text-bull-500 border-bull-500/40 bg-bull-500/10">
      Confirmed · {sources.length} sources
    </span>
  ) : (
    <span className="text-[9px] uppercase tracking-wider rounded px-1.5 py-0.5 border text-mist-400 border-ink-600 bg-ink-800">
      Unverified · 1 source
    </span>
  )
}

function DriftCard({ item, index }) {
  // Deterministic pseudo-random placement so layout is stable per render
  const top = 6 + ((index * 137) % 78)
  const duration = 55 + ((index * 61) % 65)
  const delay = -(((index * 97) % duration))
  return (
    <a href={item.url} target="_blank" rel="noreferrer"
       className="drift block w-80 bg-ink-900/70 border border-ink-700/80 rounded-lg px-3.5 py-2.5 backdrop-blur-[2px] hover:border-brass-400/50"
       style={{ top: `${top}%`, animationDuration: `${duration}s`, animationDelay: `${delay}s` }}>
      <p className="text-xs text-mist-200 leading-snug line-clamp-2">{item.title}</p>
      <div className="flex items-center gap-2 mt-1.5">
        <span className="text-[10px] text-mist-400 truncate">{item.source_name}</span>
        <span className="text-[10px] text-mist-400/70 shrink-0">{age(item.published_at)}</span>
        <span className="ml-auto shrink-0"><Badge confirmed={item.confirmed} sources={item.corroborated_by} /></span>
      </div>
    </a>
  )
}

export default function Pulse({ onOpenSymbol }) {
  const [news, setNews] = useState(null)
  const [overview, setOverview] = useState([])
  const [plans, setPlans] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    api.newsMarket().then((d) => alive && setNews(d)).catch((e) => alive && setError(e.message))
    api.marketsOverview().then((d) => alive && setOverview(d.items || [])).catch(() => {})
    api.myPlans().then((d) => alive && setPlans(d || [])).catch(() => {})
    const t = setInterval(() => api.newsMarket().then((d) => alive && setNews(d)).catch(() => {}), 5 * 60 * 1000)
    return () => { alive = false; clearInterval(t) }
  }, [])

  const skyItems = useMemo(() => (news?.items || []).slice(0, 16), [news])
  const listItems = useMemo(() => (news?.items || []).slice(0, 10), [news])

  return (
    <div className="relative min-h-[70vh] rise-in">
      {/* Background: the drifting real-headline sky */}
      <div className="news-sky" aria-hidden={skyItems.length === 0}>
        {skyItems.map((item, i) => <DriftCard key={item.id} item={item} index={i} />)}
      </div>

      {/* Foreground */}
      <div className="relative z-10 pointer-events-none">
        <div className="pointer-events-auto inline-block bg-ink-950/70 backdrop-blur rounded-xl px-1 py-1">
          <h1 className="font-[family-name:var(--font-display)] text-mist-50 text-2xl font-semibold px-3 pt-2">Market Pulse</h1>
          <p className="text-xs text-mist-400 px-3 pb-2">
            {news
              ? `${news.items.length} live stories · ${news.confirmed_count} confirmed by 2+ sources · every card links to the original article`
              : error || 'Fetching real headlines…'}
          </p>
        </div>

        {/* Market pulse cards */}
        <div className="pointer-events-auto flex flex-wrap gap-2.5 mt-4 max-w-3xl">
          {overview.slice(0, 6).map((it) => {
            const up = it.change_pct >= 0
            return (
              <button key={it.symbol} onClick={() => onOpenSymbol(it.symbol)}
                      className="bg-ink-900/85 backdrop-blur border border-ink-700 hover:border-brass-400/50 rounded-lg px-3.5 py-2.5 text-left transition-colors">
                <span className="text-[10px] uppercase tracking-wider text-mist-400 block">{it.name}</span>
                <span className="price text-sm text-mist-50">{it.currency}{it.price?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                <span className={`price text-[11px] ml-2 ${up ? 'text-bull-500' : 'text-bear-500'}`}>
                  {up ? '▲' : '▼'}{Math.abs(it.change_pct ?? 0).toFixed(2)}%
                </span>
              </button>
            )
          })}
        </div>

        {/* Recent saved setups */}
        {plans.length > 0 && (
          <div className="pointer-events-auto mt-5 bg-ink-900/85 backdrop-blur border border-ink-700 rounded-xl p-4 max-w-xl">
            <h3 className="text-xs uppercase tracking-wider text-brass-400 mb-2">Your recent setups</h3>
            <ul className="space-y-1.5">
              {plans.slice(0, 4).map((p) => (
                <li key={p.id}>
                  <button onClick={() => onOpenSymbol(p.symbol)}
                          className="w-full flex items-center gap-3 text-left hover:bg-ink-800 rounded px-2 py-1">
                    <span className="price text-xs text-mist-50">{p.symbol}</span>
                    <span className="text-[10px] text-mist-400 uppercase tracking-wider">{p.setup_state?.replaceAll('_', ' ')}</span>
                    <span className="price text-[11px] text-mist-400 ml-auto">conf {p.confidence}/100</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <TrackRecord onOpenSymbol={onOpenSymbol} />

        {/* Top stories, readable list */}
        <div className="pointer-events-auto mt-5 bg-ink-900/85 backdrop-blur border border-ink-700 rounded-xl p-4 max-w-2xl">
          <h3 className="text-xs uppercase tracking-wider text-mist-400 mb-2.5">Top stories right now</h3>
          <ul className="space-y-2">
            {listItems.map((item) => (
              <li key={item.id}>
                <a href={item.url} target="_blank" rel="noreferrer" className="group flex items-start gap-2.5">
                  <span className="flex-1 text-sm text-mist-200 group-hover:text-mist-50 leading-snug">{item.title}</span>
                  <span className="shrink-0 flex flex-col items-end gap-1">
                    <Badge confirmed={item.confirmed} sources={item.corroborated_by} />
                    <span className="text-[10px] text-mist-400">{item.source_name} · {age(item.published_at)}</span>
                  </span>
                </a>
              </li>
            ))}
            {news && news.items.length === 0 && (
              <li className="text-sm text-mist-400">
                No feeds reachable right now{news.feeds_failed?.length ? ` (${news.feeds_failed.join(', ')})` : ''} — retrying every 5 minutes.
              </li>
            )}
          </ul>
          {news?.feeds_failed?.length > 0 && news.items.length > 0 && (
            <p className="text-[10px] text-mist-400/70 mt-2.5">Unreachable feeds: {news.feeds_failed.join(', ')}</p>
          )}
        </div>
      </div>
    </div>
  )
}
