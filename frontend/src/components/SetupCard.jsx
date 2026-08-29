import { useState } from 'react'
import SourceFooter from './SourceFooter'

function PositionSizer({ plan, currencySign }) {
  const [capital, setCapital] = useState(() => Number(localStorage.getItem('sl_capital')) || 100000)
  const [riskPct, setRiskPct] = useState(() => Number(localStorage.getItem('sl_risk_pct')) || 1)
  const entryMid = (plan.entry_low + plan.entry_high) / 2
  const perShareRisk = entryMid - plan.stop_loss
  const riskAmount = capital * (riskPct / 100)
  const qty = perShareRisk > 0 ? Math.floor(riskAmount / perShareRisk) : 0
  const outlay = qty * entryMid
  const save = (k, v, set) => { set(v); localStorage.setItem(k, String(v)) }
  return (
    <div className="mt-4 bg-ink-800/60 border border-ink-600/60 rounded-lg px-3.5 py-3">
      <div className="text-[10px] uppercase tracking-wider text-brass-400 mb-2">Position size calculator</div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-[10px] text-mist-400">
          Capital ({currencySign})
          <input type="number" value={capital}
                 onChange={(e) => save('sl_capital', Number(e.target.value) || 0, setCapital)}
                 className="block mt-0.5 w-28 bg-ink-900 border border-ink-600 rounded px-2 py-1 text-xs text-mist-50 price" />
        </label>
        <label className="text-[10px] text-mist-400">
          Risk per trade (%)
          <input type="number" step="0.5" min="0.1" max="10" value={riskPct}
                 onChange={(e) => save('sl_risk_pct', Number(e.target.value) || 1, setRiskPct)}
                 className="block mt-0.5 w-20 bg-ink-900 border border-ink-600 rounded px-2 py-1 text-xs text-mist-50 price" />
        </label>
        <div className="price text-xs text-mist-200 leading-relaxed">
          → <span className="text-mist-50 text-sm">{qty}</span> shares
          <span className="text-mist-400"> · outlay ~{currencySign}{outlay.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          · risking {currencySign}{riskAmount.toLocaleString(undefined, { maximumFractionDigits: 0 })} if the stop hits</span>
        </div>
      </div>
      <p className="text-[9px] text-mist-400/60 mt-1.5">Classic fixed-fractional sizing: shares = (capital × risk%) ÷ (entry − stop). Education, not advice.</p>
    </div>
  )
}

const stateLabel = (s) => (s || '').replaceAll('_', ' ').toUpperCase()

const NARRATION_BLOCKS = [
  ['pattern', 'The pattern'],
  ['why', 'Why it matters'],
  ['confirmation', 'What confirms it'],
  ['invalidation', 'What kills it'],
]

function Tile({ label, value, tone = 'text-mist-50' }) {
  return (
    <div className="bg-ink-800 border border-ink-600 rounded-lg px-3.5 py-3">
      <div className="text-[10px] uppercase tracking-wider text-mist-400">{label}</div>
      <div className={`price text-lg mt-1 ${tone}`}>{value}</div>
    </div>
  )
}

export default function SetupCard({ analysis, currencySign }) {
  if (!analysis) return null
  const { setup, narration, verification, indicators, source } = analysis
  const plan = setup.plan
  const cs = currencySign || ''
  const fmt = (v) => (v == null ? '—' : `${cs}${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`)

  const verBadge =
    verification?.status === 'verified'
      ? { text: 'Verified against data', cls: 'text-bull-500 border-bull-500/40 bg-bull-500/10' }
      : verification?.status === 'edited'
      ? { text: `Verified — ${verification.unsupported_sentences_removed} unsupported line(s) removed`, cls: 'text-brass-400 border-brass-400/40 bg-brass-400/10' }
      : { text: 'Built from computed facts (local AI offline)', cls: 'text-mist-400 border-ink-600 bg-ink-800' }

  return (
    <section className="rise-in bg-ink-900 border border-ink-700 rounded-xl p-4 sm:p-5 mt-5">
      {/* Header: state + bias + confidence */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-[family-name:var(--font-display)] text-mist-50 font-semibold tracking-tight">
          {stateLabel(setup.state)}
        </span>
        <span className={`text-[10px] uppercase tracking-wider rounded px-2 py-0.5 border ${
          setup.bias === 'bullish' ? 'text-bull-500 border-bull-500/40 bg-bull-500/10'
          : setup.bias === 'bearish' ? 'text-bear-500 border-bear-500/40 bg-bear-500/10'
          : 'text-mist-400 border-ink-600 bg-ink-800'
        }`}>
          {setup.bias}
        </span>
        {plan?.conditional && (
          <span className="text-[10px] uppercase tracking-wider rounded px-2 py-0.5 border text-brass-400 border-brass-400/40 bg-brass-400/10">
            conditional — valid only on breakout
          </span>
        )}
        {plan && (
          <div className="ml-auto flex items-center gap-2.5">
            <div className="w-28 h-2 bg-ink-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${setup.confidence >= 65 ? 'bg-bull-500' : setup.confidence >= 45 ? 'bg-brass-400' : 'bg-bear-500'}`}
                style={{ width: `${setup.confidence}%` }}
              />
            </div>
            <span className="price text-sm text-mist-50">{setup.confidence}<span className="text-mist-400 text-xs">/100</span></span>
          </div>
        )}
      </div>

      {plan ? (
        <>
          {/* The numbers — scannable, monospace, no prose */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5 mt-4">
            <Tile label="Entry zone" value={`${fmt(plan.entry_low)} – ${fmt(plan.entry_high)}`} tone="text-bull-500" />
            <Tile label="Stop-loss" value={fmt(plan.stop_loss)} tone="text-bear-500" />
            <Tile label="Target 1" value={fmt(plan.target1)} tone="text-brass-300" />
            <Tile label="Target 2" value={fmt(plan.target2)} tone="text-brass-300" />
            <Tile label="Risk : reward" value={`${plan.risk_reward} : 1`} />
          </div>

          <PositionSizer plan={plan} currencySign={cs} />

          {/* Why the confidence is what it is */}
          <div className="mt-4 grid gap-1.5">
            {setup.factors.map((f) => (
              <div key={f.name} className="flex items-center gap-3">
                <span className="text-xs text-mist-400 w-64 shrink-0 truncate" title={f.name}>{f.name}</span>
                <div className="flex-1 h-1.5 bg-ink-700 rounded-full overflow-hidden">
                  <div className="h-full bg-brass-400/70 rounded-full" style={{ width: `${(f.contribution / f.max) * 100}%` }} />
                </div>
                <span className="price text-[11px] text-mist-400 w-12 text-right">{f.contribution}/{f.max}</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="mt-4">
          <div className="bg-ink-800 border border-ink-600 rounded-lg px-4 py-3.5 text-sm text-mist-200">
            {setup.state === 'strong_uptrend_extended'
              ? 'Strong uptrend, but extended — price is stretched well above its base. Chasing here buys maximum risk; the professional move is waiting for the pullback to the levels below.'
              : setup.state === 'downtrend'
              ? 'Downtrend regime — price is below its falling averages. No long setup exists; staying out IS the trade.'
              : "No clean setup on this chart right now — and saying so is the feature. The engine refuses to invent a trade where the structure doesn't offer one."}
          </div>
          {setup.watch && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mt-3">
              {setup.watch.nearest_support ? (
                <Tile label="Nearest support zone"
                      value={`${fmt(setup.watch.nearest_support.price_low)} – ${fmt(setup.watch.nearest_support.price_high)}`}
                      tone="text-bull-500" />
              ) : (
                <Tile label="Recent swing low" value={fmt(setup.watch.recent_swing_low)} tone="text-bull-500" />
              )}
              {setup.watch.nearest_resistance ? (
                <Tile label="Nearest resistance zone"
                      value={`${fmt(setup.watch.nearest_resistance.price_low)} – ${fmt(setup.watch.nearest_resistance.price_high)}`}
                      tone="text-bear-500" />
              ) : (
                <Tile label="Recent swing high" value={fmt(setup.watch.recent_swing_high)} tone="text-bear-500" />
              )}
              <Tile label="20 SMA (pullback line)" value={fmt(setup.watch.sma20)} tone="text-brass-300" />
              <Tile label="RSI now" value={indicators.rsi14 ?? '—'} />
            </div>
          )}
        </div>
      )}

      {/* The presenter's narration — four short labeled blocks, never a wall of text */}
      <div className="grid sm:grid-cols-2 gap-2.5 mt-4">
        {NARRATION_BLOCKS.map(([key, label]) => (
          <div key={key} className="bg-ink-800/60 border border-ink-600/60 rounded-lg px-3.5 py-3">
            <div className="text-[10px] uppercase tracking-wider text-brass-400">{label}</div>
            <p className="text-sm text-mist-200 leading-relaxed mt-1">{narration?.[key] || '—'}</p>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2 mt-4">
        <span className={`text-[11px] rounded px-2 py-1 border ${verBadge.cls}`}>✓ {verBadge.text}</span>
        {analysis.saved_plan_id && (
          <span className="text-[11px] text-mist-400">Setup #{analysis.saved_plan_id} saved for future self-grading</span>
        )}
        <span className="text-[11px] price text-mist-400 ml-auto">
          RSI {indicators.rsi14 ?? '—'} · ATR {indicators.atr14 ?? '—'} · Vol {indicators.volume_ratio ?? '—'}x
        </span>
      </div>

      <SourceFooter source={source} />
      <p className="text-[10px] text-mist-400/60 mt-2">{analysis.disclaimer}</p>
    </section>
  )
}
