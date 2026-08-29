import { useEffect, useState } from 'react'
import { api } from '../api'

const STATUS_STYLE = {
  hit_t2: 'text-bull-500 border-bull-500/40 bg-bull-500/10',
  hit_t1: 'text-bull-500 border-bull-500/40 bg-bull-500/10',
  stopped: 'text-bear-500 border-bear-500/40 bg-bear-500/10',
  expired: 'text-mist-400 border-ink-600 bg-ink-800',
  open: 'text-brass-400 border-brass-400/40 bg-brass-400/10',
}

export default function TrackRecord({ onOpenSymbol }) {
  const [data, setData] = useState(null)

  useEffect(() => { api.trackRecord().then(setData).catch(() => {}) }, [])

  if (!data || data.total_plans === 0) return null
  const s = data.scorecard

  return (
    <div className="pointer-events-auto mt-5 bg-ink-900/85 backdrop-blur border border-ink-700 rounded-xl p-4 max-w-2xl">
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 className="text-xs uppercase tracking-wider text-brass-400">The engine's own track record</h3>
        <span className="text-[10px] text-mist-400">every Analyze call, graded against what price actually did</span>
      </div>
      <div className="flex flex-wrap gap-4 mt-3">
        <div>
          <span className="price text-2xl text-mist-50">{s.win_rate != null ? `${s.win_rate}%` : '—'}</span>
          <span className="block text-[10px] text-mist-400">win rate ({s.graded_closed} closed)</span>
        </div>
        <div className="price text-xs text-mist-400 self-center leading-relaxed">
          <span className="text-bull-500">{s.hit_t1 + s.hit_t2} targets hit</span> ·{' '}
          <span className="text-bear-500">{s.stopped} stopped</span> ·{' '}
          {s.open} running · {s.expired} never triggered
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5 mt-3">
        {data.plans.map((p) => (
          <button key={p.id} onClick={() => onOpenSymbol(p.symbol)}
                  title={`${p.state} · entry ${p.entry_high} stop ${p.stop_loss} T1 ${p.target1}`}
                  className={`price text-[10px] rounded-full border px-2.5 py-1 ${STATUS_STYLE[p.status] || STATUS_STYLE.open}`}>
            {p.symbol.replace('.NS', '')} · {p.status.replace('_', ' ')}
          </button>
        ))}
      </div>
      <p className="text-[9px] text-mist-400/60 mt-2.5">{s.note}</p>
    </div>
  )
}
