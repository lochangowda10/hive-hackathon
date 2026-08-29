import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import SourceFooter from '../components/SourceFooter'

const fmtMoney = (v) => (v == null ? '—' : `₹${Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`)

function Stat({ label, value, tone = 'text-mist-50', sub }) {
  return (
    <div className="bg-ink-900 border border-ink-700 rounded-xl px-4 py-3 min-w-40">
      <div className="text-[10px] uppercase tracking-wider text-mist-400">{label}</div>
      <div className={`price text-xl mt-0.5 ${tone}`}>{value}</div>
      {sub && <div className="text-[10px] text-mist-400 mt-0.5">{sub}</div>}
    </div>
  )
}

function ImportCard({ onImported }) {
  const [broker, setBroker] = useState('indmoney')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [report, setReport] = useState(null)
  const fileRef = useRef(null)

  const upload = async (file) => {
    if (!file) return
    setBusy(true)
    setError('')
    setReport(null)
    try {
      const res = await api.importPortfolio(file, broker)
      setReport(res)
      onImported()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <div className="bg-ink-900 border border-ink-700 rounded-xl p-5">
      <h3 className="font-[family-name:var(--font-display)] text-mist-50 font-semibold">Import from your broker</h3>
      <p className="text-xs text-mist-400 mt-1 leading-relaxed max-w-xl">
        Export from your broker app (look for <span className="text-mist-200">Reports / Statements</span> —
        a <span className="text-mist-200">Holdings statement</span> and/or an <span className="text-mist-200">Order
        history / tradebook</span>, CSV or Excel), then drop it here. Files are parsed on
        <span className="text-mist-200"> your own machine</span> and stored only in your local database.
        No file? Try the samples in the project's <span className="price text-brass-400">sample_data/</span> folder.
      </p>
      <div className="flex flex-wrap items-center gap-2.5 mt-4">
        <select value={broker} onChange={(e) => setBroker(e.target.value)}
                className="bg-ink-800 border border-ink-600 rounded-lg px-3 py-2 text-sm text-mist-50">
          <option value="indmoney">INDmoney</option>
          <option value="groww">Groww</option>
          <option value="zerodha">Zerodha</option>
          <option value="other">Other broker</option>
        </select>
        <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" className="hidden"
               onChange={(e) => upload(e.target.files?.[0])} />
        <button onClick={() => fileRef.current?.click()} disabled={busy}
                className="bg-brass-400 hover:bg-brass-300 disabled:opacity-60 text-ink-950 font-semibold text-sm rounded-lg px-4 py-2">
          {busy ? 'Reading your file…' : 'Choose file (.csv / .xlsx)'}
        </button>
      </div>
      {error && <p className="mt-3 text-sm text-bear-500 bg-bear-500/10 border border-bear-500/30 rounded-lg px-3 py-2">{error}</p>}
      {report && (
        <div className="rise-in mt-3 text-xs text-mist-200 bg-ink-800 border border-ink-600 rounded-lg px-3 py-2.5">
          ✓ Imported <strong>{report.imported}</strong> rows as a <strong>{report.kind}</strong> from {report.broker}
          {report.skipped > 0 && <> · {report.skipped} unreadable rows skipped</>}
          {report.unresolved_symbols > 0 && <> · {report.unresolved_symbols} symbols not matched to live quotes (still counted)</>}
          <span className="block text-mist-400 mt-0.5">{report.note}</span>
        </div>
      )}
    </div>
  )
}

export default function Portfolio({ onOpenSymbol, onPortfolio }) {
  const [summary, setSummary] = useState(null)
  const [behavior, setBehavior] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    Promise.all([
      api.portfolioSummary().catch(() => null),
      api.portfolioBehavior().catch(() => null),
    ]).then(([s, b]) => {
      setSummary(s)
      setBehavior(b)
      if (s && !s.empty) onPortfolio?.({ pnl_pct: s.pnl_pct, current: s.current, top: s.positions.slice(0, 5).map((p) => ({ name: p.name, pnl_pct: p.pnl_pct, weight_pct: p.weight_pct })) })
    }).finally(() => setLoading(false))
  }
  useEffect(load, [])

  const clearAll = async () => {
    await api.clearPortfolio().catch(() => {})
    onPortfolio?.(null)
    load()
  }

  const hasHoldings = summary && !summary.empty
  const profile = behavior && !behavior.empty ? behavior.profile : null
  const up = hasHoldings && summary.pnl >= 0

  return (
    <div className="rise-in space-y-5">
      <ImportCard onImported={load} />

      {loading && <p className="text-sm text-mist-400">Reading your portfolio…</p>}

      {hasHoldings && (
        <>
          <div className="flex flex-wrap gap-3">
            <Stat label="Invested" value={fmtMoney(summary.invested)} />
            <Stat label="Current value" value={fmtMoney(summary.current)} />
            <Stat label="Unrealized P&L" tone={up ? 'text-bull-500' : 'text-bear-500'}
                  value={`${up ? '+' : ''}${fmtMoney(summary.pnl)} (${summary.pnl_pct}%)`} />
            <Stat label="Positions" value={summary.position_count}
                  sub={`Top-3 = ${summary.top3_concentration_pct}% of portfolio`} />
            {behavior && !behavior.empty && (
              <Stat label="Realized P&L (closed trades)" tone={behavior.realized_pnl >= 0 ? 'text-bull-500' : 'text-bear-500'}
                    value={fmtMoney(behavior.realized_pnl)} sub={`${behavior.trade_count} trades imported`} />
            )}
          </div>

          <div className="bg-ink-900 border border-ink-700 rounded-xl overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-mist-400 border-b border-ink-700">
                  <th className="text-left font-medium px-4 py-2.5">Holding</th>
                  <th className="text-right font-medium px-3 py-2.5">Qty</th>
                  <th className="text-right font-medium px-3 py-2.5">Avg</th>
                  <th className="text-right font-medium px-3 py-2.5">LTP</th>
                  <th className="text-right font-medium px-4 py-2.5">P&L</th>
                  <th className="text-left font-medium px-4 py-2.5 w-40 hidden md:table-cell">Weight</th>
                </tr>
              </thead>
              <tbody>
                {summary.positions.map((p) => {
                  const pUp = p.pnl >= 0
                  return (
                    <tr key={p.symbol_raw}
                        onClick={() => p.symbol && onOpenSymbol(p.symbol)}
                        className={`border-b border-ink-800 last:border-0 hover:bg-ink-800/60 ${p.symbol ? 'cursor-pointer' : ''}`}>
                      <td className="px-4 py-2.5">
                        <span className="text-mist-50">{p.name}</span>
                        <span className="block price text-[10px] text-mist-400">
                          {p.symbol || p.symbol_raw}{p.ltp_source !== 'live' && ' · no live quote'}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-right price text-mist-200">{p.quantity}</td>
                      <td className="px-3 py-2.5 text-right price text-mist-400">{p.avg_price}</td>
                      <td className="px-3 py-2.5 text-right price text-mist-200">{p.ltp}</td>
                      <td className={`px-4 py-2.5 text-right price ${pUp ? 'text-bull-500' : 'text-bear-500'}`}>
                        {pUp ? '+' : ''}{fmtMoney(p.pnl)}<span className="block text-[10px]">{pUp ? '+' : ''}{p.pnl_pct}%</span>
                      </td>
                      <td className="px-4 py-2.5 hidden md:table-cell">
                        <div className="h-1.5 bg-ink-700 rounded-full overflow-hidden">
                          <div className="h-full bg-brass-400/70 rounded-full" style={{ width: `${Math.min(p.weight_pct, 100)}%` }} />
                        </div>
                        <span className="price text-[10px] text-mist-400">{p.weight_pct}%</span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <div className="px-4 pb-3"><SourceFooter source={summary.source} /></div>
          </div>
        </>
      )}

      {/* The Trader Mirror */}
      {behavior && !behavior.empty && (
        <div className="bg-ink-900 border border-ink-700 rounded-xl p-5">
          <h3 className="font-[family-name:var(--font-display)] text-mist-50 font-semibold">The Trader Mirror</h3>
          {!profile?.ready ? (
            <p className="text-sm text-mist-400 mt-2 max-w-xl leading-relaxed">{profile?.message}</p>
          ) : (
            <>
              {profile.badges.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {profile.badges.map((b) => (
                    <span key={b} className="text-xs text-brass-300 border border-brass-400/40 bg-brass-400/10 rounded-full px-3 py-1">{b}</span>
                  ))}
                </div>
              )}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5 mt-4">
                <Stat label="Win rate" value={`${profile.win_rate}%`} sub={`${profile.round_trips} closed trips`} />
                <Stat label="Avg win" tone="text-bull-500" value={`+${profile.avg_win_pct}%`} />
                <Stat label="Avg loss" tone="text-bear-500" value={`${profile.avg_loss_pct}%`} />
                <Stat label="Profit factor" value={profile.profit_factor ?? '∞'} />
                <Stat label="Median hold" value={profile.median_hold_days != null ? `${profile.median_hold_days}d` : '—'} />
              </div>
              <div className="grid sm:grid-cols-2 gap-2.5 mt-4">
                {profile.traits.map((t) => (
                  <div key={t.trait} className="bg-ink-800/60 border border-ink-600/60 rounded-lg px-3.5 py-3">
                    <div className="text-[10px] uppercase tracking-wider text-brass-400">{t.trait}</div>
                    <div className="text-sm text-mist-50 mt-0.5">{t.verdict}</div>
                    <p className="text-xs text-mist-400 mt-1 leading-relaxed">{t.evidence}</p>
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap gap-2.5 mt-4 text-xs">
                <span className="text-mist-400">Best trip:
                  <span className="text-bull-500 price ml-1">{profile.best_trade.name} +{fmtMoney(profile.best_trade.pnl)}</span>
                </span>
                <span className="text-mist-400">Worst trip:
                  <span className="text-bear-500 price ml-1">{profile.worst_trade.name} {fmtMoney(profile.worst_trade.pnl)}</span>
                </span>
              </div>
            </>
          )}
          <SourceFooter source={behavior.source} />
        </div>
      )}

      {(hasHoldings || (behavior && !behavior.empty)) && (
        <button onClick={clearAll}
                className="text-xs text-mist-400 hover:text-bear-500 border border-ink-600 rounded-lg px-3 py-1.5">
          Clear all imported data
        </button>
      )}
    </div>
  )
}
