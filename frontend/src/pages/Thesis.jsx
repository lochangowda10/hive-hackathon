import { useEffect, useState } from 'react'
import { api } from '../api'

const KIND_STYLE = {
  weakened: 'text-bear-500',
  strengthened: 'text-bull-500',
  stable: 'text-mist-400',
}
const KIND_ICON = { weakened: '▼', strengthened: '▲', stable: '●' }

function healthColor(h) {
  return h == null ? 'text-mist-400' : h >= 75 ? 'text-bull-500' : h >= 50 ? 'text-brass-400' : 'text-bear-500'
}

export default function ThesisMonitor({ onOpenSymbol }) {
  const [theses, setTheses] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [checkingId, setCheckingId] = useState(null)
  const [reports, setReports] = useState({}) // thesis_id -> last check result

  const load = () => {
    setLoading(true); setError('')
    api.theses()
      .then((d) => setTheses(d.theses || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const check = async (t) => {
    setCheckingId(t.id)
    try {
      const r = await api.checkThesis(t.id)
      setReports((m) => ({ ...m, [t.id]: r }))
      setTheses((ts) => ts.map((x) => x.id === t.id
        ? { ...x, last_health: r.health, last_changes: r.changes, last_checked_at: new Date().toISOString() }
        : x))
    } catch (e) { setError(e.message) } finally { setCheckingId(null) }
  }

  const remove = async (t) => {
    try { await api.deleteThesis(t.id); setTheses((ts) => ts.filter((x) => x.id !== t.id)) }
    catch { /* keep list honest */ }
  }

  return (
    <div className="rise-in space-y-4">
      <section className="bg-ink-900 border border-ink-700 rounded-xl p-4 sm:p-5">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h2 className="font-[family-name:var(--font-display)] text-mist-50 text-lg font-semibold tracking-tight">Thesis Monitor</h2>
            <p className="text-xs text-mist-400 mt-0.5">
              Saved theses are snapshots of computed numbers. Re-checking recomputes the evidence —
              health falls only when the facts that justified the thesis actually weaken.
            </p>
          </div>
        </div>

        {loading && (
          <div className="py-12 grid place-items-center">
            <span className="w-6 h-6 border-2 border-mist-400/30 border-t-brass-400 rounded-full animate-spin" />
          </div>
        )}
        {error && <p className="mt-3 text-sm text-bear-500 bg-bear-500/10 border border-bear-500/30 rounded-lg px-3 py-2">{error}</p>}

        {!loading && theses.length === 0 && !error && (
          <div className="py-12 text-center">
            <p className="text-mist-300 text-sm">No saved theses yet.</p>
            <p className="text-mist-400 text-xs mt-1">Open any stock's Research page and press <strong className="text-brass-400">Save Thesis</strong> — we'll monitor the evidence from then on.</p>
          </div>
        )}

        <div className="mt-4 space-y-3">
          {theses.map((t) => {
            const live = reports[t.id]
            return (
              <div key={t.id} className="bg-ink-800/50 border border-ink-700 rounded-lg p-4">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div>
                    <button onClick={() => onOpenSymbol?.(t.symbol)}
                            className="text-mist-50 font-medium hover:text-brass-400 transition-colors">
                      {t.name || t.symbol} <span className="text-mist-400 text-xs">{t.symbol}</span>
                    </button>
                    <div className="text-[11px] text-mist-400 mt-0.5">
                      Saved {t.created_at ? new Date(t.created_at).toLocaleDateString() : ''}
                      {t.snapshot?.verdict ? ` · verdict then: ${t.snapshot.verdict}` : ''}
                      {t.snapshot?.ai_score != null ? ` · AI ${t.snapshot.ai_score}` : ''}
                      {t.last_checked_at ? ` · checked ${new Date(t.last_checked_at).toLocaleString()}` : ''}
                    </div>
                    {t.note && <p className="text-xs text-mist-300 mt-1.5 italic">"{t.note}"</p>}
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <div className="text-[10px] uppercase tracking-wider text-mist-400">Thesis health</div>
                      <div className={`price text-2xl ${healthColor(t.last_health)}`}>
                        {t.last_health ?? '—'}<span className="text-xs text-mist-400">/100</span>
                      </div>
                    </div>
                    <button onClick={() => check(t)} disabled={checkingId === t.id}
                            className="text-xs bg-brass-400 hover:bg-brass-300 disabled:opacity-50 text-ink-950 font-semibold rounded-lg px-3 py-1.5">
                      {checkingId === t.id ? 'Recomputing…' : 'Re-check evidence'}
                    </button>
                    <button onClick={() => remove(t)} title="Delete thesis"
                            className="text-xs text-mist-400 hover:text-bear-500 border border-ink-600 rounded-lg px-2.5 py-1.5">✕</button>
                  </div>
                </div>

                {(live?.changes || t.last_changes || []).length > 0 && (
                  <ul className="mt-3 space-y-1 border-t border-ink-700 pt-3">
                    {(live?.changes || t.last_changes || []).map((c, i) => (
                      <li key={i} className={`text-xs flex gap-2 ${KIND_STYLE[c.kind] || 'text-mist-300'}`}>
                        <span>{KIND_ICON[c.kind] || '•'}</span><span>{c.text}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {live?.current_thesis?.why_not?.length > 0 && (
                  <p className="mt-2 text-[11px] text-mist-400">
                    Current top risks: {live.current_thesis.why_not.slice(0, 2).join(' · ')}
                  </p>
                )}
              </div>
            )
          })}
        </div>
        <p className="mt-4 text-[10px] text-mist-400/60">Thesis health is computed from score and valuation drift — not from price alone, and never from AI opinion.</p>
      </section>
    </div>
  )
}
