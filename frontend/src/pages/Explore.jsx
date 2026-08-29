import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import SourceFooter from '../components/SourceFooter'

function Spark({ points, up }) {
  if (!points || points.length < 2) return <span className="w-20" />
  const min = Math.min(...points)
  const max = Math.max(...points)
  const span = max - min || 1
  const pts = points.map((p, i) =>
    `${(i / (points.length - 1)) * 76 + 2},${22 - ((p - min) / span) * 18}`
  ).join(' ')
  return (
    <svg width="80" height="26" className="shrink-0" aria-hidden="true">
      <polyline points={pts} fill="none" stroke={up ? '#22c07a' : '#ef5350'} strokeWidth="1.5" />
    </svg>
  )
}

function MoverCard({ title, items, tone, onOpen }) {
  return (
    <div className="bg-ink-900 border border-ink-700 rounded-xl p-4 flex-1 min-w-64">
      <h3 className={`text-xs uppercase tracking-wider ${tone} mb-2.5`}>{title}</h3>
      <ul className="space-y-1.5">
        {items.map((r) => (
          <li key={r.symbol}>
            <button onClick={() => onOpen(r.symbol)}
                    className="w-full flex items-center justify-between gap-2 text-left hover:bg-ink-800 rounded px-2 py-1">
              <span className="text-sm text-mist-200 truncate">{r.name}</span>
              <span className={`price text-xs shrink-0 ${r.change_pct >= 0 ? 'text-bull-500' : 'text-bear-500'}`}>
                {r.change_pct >= 0 ? '▲' : '▼'} {Math.abs(r.change_pct).toFixed(2)}%
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function Explore({ onOpenSymbol }) {
  const [segments, setSegments] = useState([])
  const [current, setCurrent] = useState('india_large')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.marketSegments().then((d) => setSegments(d.segments || [])).catch(() => {})
  }, [])

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError('')
    api.marketSegment(current)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [current])

  const groups = useMemo(() => {
    const g = []
    for (const s of segments) {
      const found = g.find((x) => x.group === s.group)
      if (found) found.items.push(s)
      else g.push({ group: s.group, items: [s] })
    }
    return g
  }, [segments])

  const currentGroup = segments.find((s) => s.id === current)?.group
  const subTabs = groups.find((g) => g.group === currentGroup)?.items || []
  const gainers = (data?.items || []).slice(0, 5)
  const losers = [...(data?.items || [])].slice(-5).reverse()

  return (
    <div className="rise-in">
      {/* Group tabs (Indian Stocks / US Stocks / ETFs / Commodities / Crypto) */}
      <div className="flex flex-wrap gap-2 mb-3">
        {groups.map((g) => (
          <button key={g.group}
                  onClick={() => setCurrent(g.items[0].id)}
                  className={`text-sm rounded-lg px-3.5 py-1.5 border transition-colors ${
                    currentGroup === g.group
                      ? 'border-brass-400/60 text-brass-400 bg-brass-400/10'
                      : 'border-ink-600 text-mist-400 hover:text-mist-50 hover:border-ink-500'
                  }`}>
            {g.group}
          </button>
        ))}
      </div>

      {/* Cap / sub-segment pills (Large / Mid / Small), INDmoney style */}
      {subTabs.length > 1 && (
        <div className="flex flex-wrap gap-1.5 mb-4">
          {subTabs.map((s) => (
            <button key={s.id} onClick={() => setCurrent(s.id)}
                    className={`text-xs rounded-full px-3 py-1 border transition-colors ${
                      current === s.id ? 'border-mist-200/50 text-mist-50 bg-ink-700'
                      : 'border-ink-600 text-mist-400 hover:text-mist-50'
                    }`}>
              {s.label}
            </button>
          ))}
        </div>
      )}

      {data?.note && (
        <p className="text-[11px] text-brass-400/90 mb-3">{data.note}</p>
      )}
      {error && (
        <p className="text-sm text-bear-500 bg-bear-500/10 border border-bear-500/30 rounded-lg px-3 py-2 mb-4">{error}</p>
      )}

      {/* Movers */}
      {data && (
        <div className="flex flex-wrap gap-4 mb-5">
          <MoverCard title="Top gainers" items={gainers} tone="text-bull-500" onOpen={onOpenSymbol} />
          <MoverCard title="Top losers" items={losers} tone="text-bear-500" onOpen={onOpenSymbol} />
        </div>
      )}

      {/* Full table */}
      <div className="bg-ink-900 border border-ink-700 rounded-xl overflow-x-auto relative">
        {loading && (
          <div className="absolute inset-0 grid place-items-center bg-ink-900/60 backdrop-blur-[1px] z-10">
            <span className="w-6 h-6 border-2 border-mist-400/30 border-t-brass-400 rounded-full animate-spin" />
          </div>
        )}
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px] uppercase tracking-wider text-mist-400 border-b border-ink-700">
              <th className="text-left font-medium px-4 py-2.5">Name</th>
              <th className="text-left font-medium px-2 py-2.5 hidden sm:table-cell">7d</th>
              <th className="text-right font-medium px-4 py-2.5">Price / 1D change</th>
              <th className="text-right font-medium px-4 py-2.5 hidden md:table-cell">Volume</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items || []).map((r) => {
              const up = r.change_pct >= 0
              return (
                <tr key={r.symbol}
                    onClick={() => onOpenSymbol(r.symbol)}
                    className="border-b border-ink-800 last:border-0 hover:bg-ink-800/60 cursor-pointer">
                  <td className="px-4 py-2.5">
                    <span className="text-mist-50">{r.name}</span>
                    <span className="block price text-[10px] text-mist-400">{r.symbol}</span>
                  </td>
                  <td className="px-2 py-1 hidden sm:table-cell"><Spark points={r.spark} up={up} /></td>
                  <td className="px-4 py-2.5 text-right">
                    <span className="price text-mist-50">{r.currency}{r.price?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                    <span className={`block price text-[11px] ${up ? 'text-bull-500' : 'text-bear-500'}`}>
                      {up ? '▲' : '▼'} {Math.abs(r.change ?? 0).toFixed(2)} ({Math.abs(r.change_pct ?? 0).toFixed(2)}%)
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right price text-xs text-mist-400 hidden md:table-cell">
                    {r.volume ? r.volume.toLocaleString() : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {data && <div className="px-4 pb-3"><SourceFooter source={data.source} /></div>}
      </div>
    </div>
  )
}
