import { useEffect, useState } from 'react'
import { api } from '../api'

const age = (iso) => {
  if (!iso) return ''
  const mins = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 60000))
  if (mins < 60) return `${mins}m`
  const h = Math.round(mins / 60)
  return h < 24 ? `${h}h` : `${Math.round(h / 24)}d`
}

export default function SymbolNews({ symbol, onLoaded }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let alive = true
    setLoading(true)
    setData(null)
    api.newsSymbol(symbol)
      .then((d) => { if (!alive) return; setData(d); onLoaded?.(d.items || []) })
      .catch(() => alive && setData({ items: [] }))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [symbol])

  return (
    <aside className="bg-ink-900 border border-ink-700 rounded-xl p-4">
      <div className="flex items-baseline gap-2 mb-2.5">
        <h3 className="font-[family-name:var(--font-display)] text-sm font-semibold text-mist-50">News</h3>
        <span className="price text-[10px] text-mist-400 truncate">{data?.query_name || symbol}</span>
      </div>
      {loading ? (
        <p className="text-xs text-mist-400">Fetching real headlines…</p>
      ) : (data?.items || []).length === 0 ? (
        <p className="text-xs text-mist-400">No recent stories found for this symbol.</p>
      ) : (
        <ul className="space-y-2.5">
          {data.items.slice(0, 8).map((item) => (
            <li key={item.id}>
              <a href={item.url} target="_blank" rel="noreferrer" className="group block">
                <p className="text-xs text-mist-200 group-hover:text-mist-50 leading-snug line-clamp-2">{item.title}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className={`text-[9px] uppercase tracking-wider rounded px-1 py-0.5 border ${
                    item.confirmed
                      ? 'text-bull-500 border-bull-500/40 bg-bull-500/10'
                      : 'text-mist-400 border-ink-600 bg-ink-800'
                  }`}>
                    {item.confirmed ? `Confirmed ×${item.corroborated_by.length}` : 'Unverified'}
                  </span>
                  <span className="text-[10px] text-mist-400 truncate">{item.source_name}</span>
                  <span className="text-[10px] text-mist-400/70 ml-auto shrink-0">{age(item.published_at)}</span>
                </div>
              </a>
            </li>
          ))}
        </ul>
      )}
    </aside>
  )
}
