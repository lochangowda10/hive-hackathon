export default function WatchStrip({ items, symbol, onOpen, onRemove, fallback }) {
  const list = items.length ? items : null
  return (
    <div className="flex flex-wrap items-center gap-2 mb-4">
      <span className="text-[11px] uppercase tracking-wider text-mist-400/70">
        {list ? '⭐ Watchlist' : 'Quick open'}
      </span>
      {(list || fallback.map((s) => ({ symbol: s }))).map((it) => {
        const up = (it.change_pct ?? 0) >= 0
        return (
          <span key={it.symbol} className={`group inline-flex items-center rounded-full border transition-colors ${
            symbol === it.symbol ? 'border-brass-400/60 bg-brass-400/10' : 'border-ink-600 hover:border-ink-500'
          }`}>
            <button onClick={() => onOpen(it.symbol)} className="price text-xs pl-3 py-1 text-mist-200 hover:text-mist-50">
              {it.symbol.replace('.NS', '').replace('.BO', '')}
              {it.price != null && (
                <span className={`ml-1.5 ${up ? 'text-bull-500' : 'text-bear-500'}`}>
                  {up ? '▲' : '▼'}{Math.abs(it.change_pct).toFixed(1)}%
                </span>
              )}
            </button>
            {list ? (
              <button onClick={() => onRemove(it.symbol)} title="Remove from watchlist"
                      className="px-1.5 py-1 text-mist-400/0 group-hover:text-mist-400 hover:!text-bear-500 text-xs">×</button>
            ) : <span className="pr-3" />}
          </span>
        )
      })}
    </div>
  )
}
