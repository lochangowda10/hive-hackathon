import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'

const CATEGORIES = ['All', 'Trend', 'Momentum', 'Volatility', 'Volume', 'Levels']
const LEVEL_STYLE = {
  beginner: 'text-bull-500 border-bull-500/40 bg-bull-500/10',
  intermediate: 'text-brass-400 border-brass-400/40 bg-brass-400/10',
  advanced: 'text-purple-400 border-purple-400/40 bg-purple-400/10',
}

export default function IndicatorDialog({ open, onClose, onAdd, activeIds }) {
  const [catalog, setCatalog] = useState([])
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('All')
  const [expanded, setExpanded] = useState(null)

  useEffect(() => {
    if (open && catalog.length === 0) {
      api.indicatorCatalog().then((d) => setCatalog(d.indicators)).catch(() => {})
    }
  }, [open, catalog.length])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return catalog.filter((i) =>
      (category === 'All' || i.category === category) &&
      (!q || i.name.toLowerCase().includes(q) || i.id.includes(q) || i.description.toLowerCase().includes(q))
    )
  }, [catalog, query, category])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-[2px] grid place-items-center p-4" onMouseDown={onClose}>
      <div
        className="rise-in w-full max-w-2xl max-h-[80vh] bg-ink-900 border border-ink-600 rounded-xl flex flex-col overflow-hidden shadow-2xl shadow-black/60"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="flex items-center gap-3 px-5 py-4 border-b border-ink-700">
          <h3 className="font-[family-name:var(--font-display)] text-mist-50 font-semibold">Indicators</h3>
          <span className="text-[11px] text-mist-400">every entry explains itself — built for beginners, tuned for pros</span>
          <button onClick={onClose} className="ml-auto text-mist-400 hover:text-mist-50 text-xl leading-none px-1">×</button>
        </header>

        <div className="px-5 pt-4 flex flex-col gap-3">
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search — RSI, supertrend, volume…"
            className="w-full bg-ink-800 border border-ink-600 rounded-lg px-3.5 py-2 text-sm text-mist-50 placeholder-mist-400/50 focus:border-brass-400 focus:outline-none"
          />
          <div className="flex flex-wrap gap-1.5">
            {CATEGORIES.map((c) => (
              <button
                key={c}
                onClick={() => setCategory(c)}
                className={`text-xs rounded-full px-3 py-1 border transition-colors ${
                  category === c ? 'border-brass-400/60 text-brass-400 bg-brass-400/10'
                  : 'border-ink-600 text-mist-400 hover:text-mist-50'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
        </div>

        <ul className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
          {filtered.map((ind) => {
            const isOpen = expanded === ind.id
            const already = activeIds.includes(ind.id)
            return (
              <li key={ind.id} className="rounded-lg border border-transparent hover:border-ink-600 hover:bg-ink-800/50">
                <button className="w-full flex items-center gap-3 px-3 py-2.5 text-left"
                        onClick={() => setExpanded(isOpen ? null : ind.id)}>
                  <span className="text-sm text-mist-50 font-medium">{ind.name}</span>
                  <span className={`text-[9px] uppercase tracking-wider rounded px-1.5 py-0.5 border ${LEVEL_STYLE[ind.level]}`}>
                    {ind.level}
                  </span>
                  <span className="text-[10px] text-mist-400 ml-auto shrink-0">{ind.category} · {ind.pane === 'overlay' ? 'on chart' : 'sub-pane'}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); onAdd(ind) }}
                    className="shrink-0 text-xs bg-brass-400 hover:bg-brass-300 text-ink-950 font-semibold rounded px-2.5 py-1"
                  >
                    {already ? '+ Add another' : '+ Add'}
                  </button>
                </button>
                {isOpen && (
                  <div className="px-3 pb-3 text-xs leading-relaxed">
                    <p className="text-mist-200">{ind.description}</p>
                    <p className="text-mist-400 mt-1.5">
                      <span className="text-brass-400 uppercase tracking-wider text-[9px] mr-1.5">How to read</span>
                      {ind.how_to_read}
                    </p>
                  </div>
                )}
              </li>
            )
          })}
          {filtered.length === 0 && (
            <li className="text-center text-sm text-mist-400 py-8">Nothing matches — try another word.</li>
          )}
        </ul>
      </div>
    </div>
  )
}
