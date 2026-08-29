import { useEffect, useState } from 'react'
import { api } from '../api'
import SourceFooter from '../components/SourceFooter'

const BAND_STYLE = {
  'Excellent': 'text-bull-500 bg-bull-500/10 border-bull-500/30',
  'Great': 'text-bull-500 bg-bull-500/10 border-bull-500/30',
  'Good': 'text-bull-500 bg-bull-500/10 border-bull-500/30',
  'Fair': 'text-brass-400 bg-brass-400/10 border-brass-400/30',
  'Weak': 'text-bear-500 bg-bear-500/10 border-bear-500/30',
  'Poor': 'text-bear-500 bg-bear-500/10 border-bear-500/30',
  'Very Weak': 'text-bear-500 bg-bear-500/10 border-bear-500/30',
  'Low': 'text-bull-500 bg-bull-500/10 border-bull-500/30',
  'Moderate': 'text-brass-400 bg-brass-400/10 border-brass-400/30',
  'High': 'text-bear-500 bg-bear-500/10 border-bear-500/30',
  'Very High': 'text-bear-500 bg-bear-500/10 border-bear-500/30',
  'MINIMAL': 'text-bull-500 bg-bull-500/10 border-bull-500/30',
  'LOW': 'text-bull-500 bg-bull-500/10 border-bull-500/30',
  'MODERATE': 'text-brass-400 bg-brass-400/10 border-brass-400/30',
  'HIGH': 'text-bear-500 bg-bear-500/10 border-bear-500/30',
  'Exceptional': 'text-bull-500 bg-bull-500/10 border-bull-500/30',
  'Strong': 'text-bull-500 bg-bull-500/10 border-bull-500/30',
  'Attractive': 'text-bull-500 bg-bull-500/10 border-bull-500/30',
  'Watchlist': 'text-brass-400 bg-brass-400/10 border-brass-400/30',
  'Neutral': 'text-mist-300 bg-ink-700/40 border-ink-600',
  'Avoid': 'text-bear-500 bg-bear-500/10 border-bear-500/30',
}

const VERDICT_STYLE = {
  'STRONG BUY': 'text-bull-500 border-bull-500/50 bg-bull-500/10',
  'BUY': 'text-bull-500 border-bull-500/50 bg-bull-500/10',
  'ACCUMULATE': 'text-bull-500 border-bull-500/40 bg-bull-500/5',
  'WATCH': 'text-brass-400 border-brass-400/40 bg-brass-400/5',
  'HOLD': 'text-mist-200 border-ink-500 bg-ink-800',
  'REDUCE': 'text-bear-500 border-bear-500/40 bg-bear-500/5',
  'SELL': 'text-bear-500 border-bear-500/50 bg-bear-500/10',
  'STRONG SELL': 'text-bear-500 border-bear-500/60 bg-bear-500/15',
}

function Badge({ label, value, band }) {
  const style = BAND_STYLE[band] || 'text-mist-300 bg-ink-700/40 border-ink-600'
  return (
    <div className="bg-ink-800/60 border border-ink-700 rounded-lg p-3">
      <div className="text-[10px] uppercase tracking-wider text-mist-400">{label}</div>
      <div className="mt-1.5 flex items-baseline gap-2">
        {value != null && <span className="price text-mist-50 text-lg">{value}</span>}
        {band && <span className={`text-[10px] px-1.5 py-0.5 rounded border ${style}`}>{band}</span>}
      </div>
    </div>
  )
}

function FairValueBand({ fv, currency }) {
  if (!fv?.available) {
    return <p className="text-sm text-mist-400">{fv?.note || 'Fair value unavailable - insufficient data.'}</p>
  }
  const { bear, conservative, base, bull, current_price } = fv
  const lo = Math.min(bear, current_price) * 0.97
  const hi = Math.max(bull, current_price) * 1.03
  const pct = (v) => `${Math.min(Math.max(((v - lo) / (hi - lo)) * 100, 0), 100)}%`
  const up = (fv.upside_pct ?? 0) >= 0
  return (
    <div>
      <div className="flex items-baseline gap-4 flex-wrap">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-mist-400">Base fair value</div>
          <div className="price text-2xl text-mist-50">{currency}{base?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider text-mist-400">Current price</div>
          <div className="price text-lg text-mist-200">{currency}{current_price?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</div>
        </div>
        <span className={`price text-sm px-2 py-1 rounded ${up ? 'text-bull-500 bg-bull-500/10' : 'text-bear-500 bg-bear-500/10'}`}>
          {up ? '+' : ''}{fv.upside_pct}% upside
        </span>
        <span className="text-[10px] text-mist-400">
          {Object.keys(fv.models).length} models · agreement {fv.model_agreement} · confidence {fv.confidence}%
        </span>
      </div>
      {/* scenario band */}
      <div className="relative h-10 mt-4 mb-1">
        <div className="absolute inset-x-0 top-4 h-1.5 rounded-full bg-gradient-to-r from-bear-500/40 via-brass-400/40 to-bull-500/40" />
        {[['Bear', bear], ['Conservative', conservative], ['Base', base], ['Bull', bull]].map(([label, v]) => (
          <div key={label} className="absolute top-0 -translate-x-1/2 text-center" style={{ left: pct(v) }}>
            <div className="price text-[10px] text-mist-300">{currency}{Math.round(v)}</div>
            <div className="w-px h-3 bg-mist-400/60 mx-auto my-0.5" />
            <div className="text-[9px] uppercase tracking-wider text-mist-400">{label}</div>
          </div>
        ))}
        <div className="absolute -translate-x-1/2" style={{ left: pct(current_price), top: '14px' }}>
          <div className="w-2.5 h-2.5 rounded-full bg-mist-50 border-2 border-ink-950" title="Current price" />
        </div>
      </div>
    </div>
  )
}

export default function Research({ symbol }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState('')

  useEffect(() => {
    let alive = true
    setLoading(true); setError(''); setData(null); setSaved(false); setSaveError('')
    api.research(symbol)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [symbol])

  const saveThesis = async () => {
    setSaving(true); setSaveError('')
    try { await api.saveThesis(symbol, ''); setSaved(true) }
    catch (e) { setSaveError(e.message) }
    finally { setSaving(false) }
  }

  const cs = data?.currency === 'INR' ? '₹' : data?.currency === 'USD' ? '$' : (data?.currency || '')

  return (
    <div className="rise-in space-y-5">
      <section className="bg-ink-900 border border-ink-700 rounded-xl p-4 sm:p-6">
        {loading && (
          <div className="py-16 grid place-items-center">
            <span className="w-6 h-6 border-2 border-mist-400/30 border-t-brass-400 rounded-full animate-spin" />
            <p className="text-xs text-mist-400 mt-3">Computing fundamentals, fair value models and scores…</p>
          </div>
        )}
        {error && !loading && (
          <p className="text-sm text-bear-500 bg-bear-500/10 border border-bear-500/30 rounded-lg px-4 py-3">{error}</p>
        )}
        {data && !loading && (
          <>
            {/* header */}
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="font-[family-name:var(--font-display)] text-mist-50 text-xl font-semibold tracking-tight">
                  {data.name} <span className="text-mist-400 text-sm font-normal">{data.symbol}</span>
                </h2>
                <p className="text-xs text-mist-400 mt-0.5">
                  {[data.sector, data.industry].filter(Boolean).join(' · ')}
                  {data.market_cap ? ` · MCap ${Intl.NumberFormat('en', { notation: 'compact' }).format(data.market_cap)}` : ''}
                  {` · FY data ${data.data_freshness || 'n/a'} · quality ${data.data_quality}/100`}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-center">
                  <div className="text-[10px] uppercase tracking-wider text-mist-400">AI Score</div>
                  <div className="price text-3xl text-mist-50">{data.ai_score ?? '—'}<span className="text-sm text-mist-400">/100</span></div>
                  {data.ai_band && <span className={`text-[10px] px-1.5 py-0.5 rounded border ${BAND_STYLE[data.ai_band]}`}>{data.ai_band}</span>}
                </div>
                {data.verdict && (
                  <span className={`text-sm font-semibold px-3 py-2 rounded-lg border ${VERDICT_STYLE[data.verdict]}`}>
                    {data.verdict}
                  </span>
                )}
                <button onClick={saveThesis} disabled={saving || saved}
                        title="Snapshot today's computed evidence and monitor it over time"
                        className={`text-xs font-semibold rounded-lg px-3 py-2 transition-colors ${
                          saved ? 'bg-bull-500/15 text-bull-500 border border-bull-500/40 cursor-default'
                          : 'bg-ink-800 hover:bg-ink-700 text-mist-200 border border-ink-600'
                        }`}>
                  {saved ? '✓ Thesis saved — monitoring' : saving ? 'Saving…' : 'Save Thesis'}
                </button>
              </div>
              {saveError && <p className="text-xs text-bear-500 mt-2">{saveError}</p>}
            </div>

            {/* fair value */}
            <div className="mt-5 bg-ink-800/50 border border-ink-700 rounded-lg p-4">
              <FairValueBand fv={data.fair_value} currency={cs} />
            </div>

            {/* value trap */}
            {data.value_trap?.risk !== 'MINIMAL' && (
              <div className={`mt-4 text-xs rounded-lg border px-3 py-2.5 ${BAND_STYLE[data.value_trap.risk]}`}>
                <strong>Value trap risk: {data.value_trap.risk}.</strong>{' '}
                {data.value_trap.signals.join(' · ')}
              </div>
            )}

            {/* score grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mt-5">
              <Badge label="Financial Health" value={data.scores.financial_health.score} band={data.scores.financial_health.band} />
              <Badge label="Cash Flow" value={data.scores.cash_flow.score} band={data.scores.cash_flow.band} />
              <Badge label="Growth" value={data.scores.growth.score} band={data.scores.growth.accelerating ? 'Great' : data.scores.growth.band} />
              <Badge label="Profitability" value={data.scores.profitability.score} band={data.scores.profitability.band} />
              <Badge label="Valuation" value={data.scores.valuation.score}
                     band={data.scores.valuation.upside_pct != null ? (data.scores.valuation.upside_pct > 15 ? 'Good' : data.scores.valuation.upside_pct > -10 ? 'Fair' : 'Weak') : null} />
              <Badge label="Technical" value={data.scores.technical.score} band={data.scores.technical.score >= 60 ? 'Good' : data.scores.technical.score >= 40 ? 'Fair' : data.scores.technical.score != null ? 'Weak' : null} />
              <Badge label="Risk" value={null} band={data.scores.risk.band} />
              <Badge label="Confidence" value={`${data.confidence}%`} band={null} />
            </div>

            {/* thesis */}
            <div className="grid sm:grid-cols-2 gap-4 mt-5">
              <div className="bg-ink-800/40 border border-bull-500/20 rounded-lg p-4">
                <h3 className="text-xs uppercase tracking-wider text-bull-500 mb-2">Why buy</h3>
                {data.thesis.why_buy.length ? (
                  <ul className="space-y-1.5">
                    {data.thesis.why_buy.map((t, i) => (
                      <li key={i} className="text-xs text-mist-200 leading-relaxed flex gap-2"><span className="text-bull-500">+</span>{t}</li>
                    ))}
                  </ul>
                ) : <p className="text-xs text-mist-400">No strong positive factors computed.</p>}
              </div>
              <div className="bg-ink-800/40 border border-bear-500/20 rounded-lg p-4">
                <h3 className="text-xs uppercase tracking-wider text-bear-500 mb-2">Why not</h3>
                {data.thesis.why_not.length ? (
                  <ul className="space-y-1.5">
                    {data.thesis.why_not.map((t, i) => (
                      <li key={i} className="text-xs text-mist-200 leading-relaxed flex gap-2"><span className="text-bear-500">−</span>{t}</li>
                    ))}
                  </ul>
                ) : <p className="text-xs text-mist-400">No major risk factors detected.</p>}
              </div>
            </div>

            {/* model breakdown */}
            {data.fair_value?.available && (
              <details className="mt-4">
                <summary className="text-xs text-mist-400 cursor-pointer hover:text-mist-200">Valuation model breakdown & assumptions</summary>
                <div className="mt-2 grid sm:grid-cols-2 gap-3">
                  <table className="text-xs w-full">
                    <tbody>
                      {Object.entries(data.fair_value.models).map(([k, v]) => (
                        <tr key={k} className="border-b border-ink-800">
                          <td className="py-1.5 text-mist-400">{k.replace(/_/g, ' ')}</td>
                          <td className="py-1.5 price text-mist-200 text-right">{cs}{v.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                          <td className="py-1.5 text-mist-400 text-right">{Math.round((data.fair_value.model_weights[k] || 0) * 100)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <ul className="text-[11px] text-mist-400 space-y-1">
                    {Object.values(data.fair_value.assumptions || {}).map((a, i) => <li key={i}>· {a}</li>)}
                  </ul>
                </div>
              </details>
            )}

            <p className="mt-4 text-[10px] text-mist-400/60 leading-relaxed">{data.validation_note} Research and education only — not investment advice.</p>
            <SourceFooter source={data.source} />
          </>
        )}
      </section>
    </div>
  )
}
