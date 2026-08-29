import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'

const BAND_STYLE = {
  'Excellent': 'text-bull-500', 'Great': 'text-bull-500', 'Good': 'text-bull-500',
  'Fair': 'text-brass-400', 'Weak': 'text-bear-500', 'Poor': 'text-bear-500',
  'Very Weak': 'text-bear-500', 'Low': 'text-bull-500', 'Moderate': 'text-brass-400',
  'High': 'text-bear-500', 'Very High': 'text-bear-500',
  'Exceptional': 'text-bull-500', 'Strong': 'text-bull-500', 'Attractive': 'text-bull-500',
  'Watchlist': 'text-brass-400', 'Neutral': 'text-mist-300', 'Avoid': 'text-bear-500',
}

const COLUMNS = [
  { key: 'name', label: 'Name', sortable: true },
  { key: 'price', label: 'Price', sortable: true, num: true },
  { key: 'fair_value', label: 'Fair Value', sortable: true, num: true },
  { key: 'upside_pct', label: 'Upside', sortable: true, num: true },
  { key: 'ai_score', label: 'AI Score', sortable: true, num: true },
  { key: 'verdict', label: 'Verdict', sortable: false },
  { key: 'health', label: 'Health', sortable: false },
  { key: 'cash_flow', label: 'Cash Flow', sortable: false },
  { key: 'growth', label: 'Growth', sortable: true, num: true },
  { key: 'risk', label: 'Risk', sortable: false },
]

export default function Discovery({ onOpenSymbol }) {
  const [lists, setLists] = useState([])
  const [listId, setListId] = useState('most_undervalued')
  const [universe, setUniverse] = useState('india_large')
  const [rows, setRows] = useState([])
  const [label, setLabel] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [q, setQ] = useState('')
  const [sort, setSort] = useState({ key: null, desc: true })

  useEffect(() => {
    api.discoveryLists().then((d) => setLists(d.lists || [])).catch(() => {})
  }, [])

  useEffect(() => {
    let alive = true
    setLoading(true); setError('')
    api.discovery(listId, universe)
      .then((d) => { if (alive) { setRows(d.rows || []); setLabel(d.label) } })
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [listId, universe])

  const view = useMemo(() => {
    let out = rows
    if (q.trim()) {
      const needle = q.trim().toLowerCase()
      out = out.filter((r) => r.name.toLowerCase().includes(needle) || r.symbol.toLowerCase().includes(needle))
    }
    if (sort.key) {
      out = [...out].sort((a, b) => {
        const av = a[sort.key], bv = b[sort.key]
        if (av == null) return 1
        if (bv == null) return -1
        const cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv))
        return sort.desc ? -cmp : cmp
      })
    }
    return out
  }, [rows, q, sort])

  const toggleSort = (key) =>
    setSort((s) => s.key === key ? { key, desc: !s.desc } : { key, desc: true })

  return (
    <div className="rise-in space-y-4">
      <section className="bg-ink-900 border border-ink-700 rounded-xl p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-2">
          {lists.map((l) => (
            <button key={l.id} onClick={() => setListId(l.id)}
                    className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
                      listId === l.id ? 'bg-brass-400 text-ink-950 font-semibold' : 'text-mist-300 bg-ink-800 hover:bg-ink-700 border border-ink-600'
                    }`}>
              {l.label}
            </button>
          ))}
          <select value={universe} onChange={(e) => setUniverse(e.target.value)}
                  className="ml-auto text-xs bg-ink-800 border border-ink-600 text-mist-200 rounded-lg px-2.5 py-1.5">
            <option value="india_large">India Large Cap</option>
            <option value="india_mid">India Mid Cap</option>
            <option value="india_small">India Small Cap</option>
            <option value="us">US Stocks</option>
          </select>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter…"
                 className="text-xs bg-ink-800 border border-ink-600 text-mist-50 rounded-lg px-2.5 py-1.5 w-36 focus:border-brass-400 focus:outline-none" />
        </div>

        {loading && (
          <div className="py-14 grid place-items-center">
            <span className="w-6 h-6 border-2 border-mist-400/30 border-t-brass-400 rounded-full animate-spin" />
            <p className="text-xs text-mist-400 mt-3">Scoring the universe — fundamentals, fair value models, risk…</p>
          </div>
        )}
        {error && !loading && (
          <p className="mt-4 text-sm text-bear-500 bg-bear-500/10 border border-bear-500/30 rounded-lg px-4 py-3">{error}</p>
        )}

        {!loading && !error && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-mist-400 border-b border-ink-700">
                  {COLUMNS.map((c) => (
                    <th key={c.key}
                        onClick={() => c.sortable && toggleSort(c.key)}
                        className={`py-2 pr-4 font-medium whitespace-nowrap ${c.sortable ? 'cursor-pointer hover:text-mist-200' : ''} ${c.num ? 'text-right' : ''}`}>
                      {c.label}{sort.key === c.key ? (sort.desc ? ' ↓' : ' ↑') : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {view.map((r) => (
                  <tr key={r.symbol} onClick={() => onOpenSymbol?.(r.symbol)}
                      className="border-b border-ink-800 hover:bg-ink-800/50 cursor-pointer">
                    <td className="py-2.5 pr-4">
                      <div className="text-mist-50">{r.name}</div>
                      <div className="text-mist-400 text-[10px]">{r.symbol}</div>
                    </td>
                    <td className="py-2.5 pr-4 price text-right text-mist-200">{r.price?.toLocaleString(undefined, { maximumFractionDigits: 2 }) ?? '—'}</td>
                    <td className="py-2.5 pr-4 price text-right text-mist-200">{r.fair_value?.toLocaleString(undefined, { maximumFractionDigits: 0 }) ?? '—'}</td>
                    <td className={`py-2.5 pr-4 price text-right ${r.upside_pct == null ? 'text-mist-400' : r.upside_pct >= 0 ? 'text-bull-500' : 'text-bear-500'}`}>
                      {r.upside_pct == null ? '—' : `${r.upside_pct >= 0 ? '+' : ''}${r.upside_pct}%`}
                    </td>
                    <td className="py-2.5 pr-4 price text-right">
                      <span className={BAND_STYLE[r.ai_band] || 'text-mist-200'}>{r.ai_score ?? '—'}</span>
                    </td>
                    <td className="py-2.5 pr-4 text-mist-200 whitespace-nowrap">{r.verdict || '—'}</td>
                    <td className={`py-2.5 pr-4 ${BAND_STYLE[r.health] || 'text-mist-300'}`}>{r.health || '—'}</td>
                    <td className={`py-2.5 pr-4 ${BAND_STYLE[r.cash_flow] || 'text-mist-300'}`}>{r.cash_flow || '—'}</td>
                    <td className="py-2.5 pr-4 price text-right text-mist-200">{r.growth ?? '—'}</td>
                    <td className={`py-2.5 ${BAND_STYLE[r.risk] || 'text-mist-300'}`}>{r.risk || '—'}</td>
                  </tr>
                ))}
                {view.length === 0 && (
                  <tr><td colSpan={COLUMNS.length} className="py-8 text-center text-mist-400">No stocks matched.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-3 text-[10px] text-mist-400/60 leading-relaxed">
          {label}: ranked by scores computed from reported financials and price math. Value traps are excluded
          from undervaluation lists. Research and education only — not investment advice.
        </p>
      </section>
    </div>
  )
}
