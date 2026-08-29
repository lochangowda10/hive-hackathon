import { useEffect, useRef, useState } from 'react'
import {
  HistogramSeries, LineSeries, LineStyle, createChart, createSeriesMarkers,
} from 'lightweight-charts'
import { api } from '../api'
import IndicatorChips from './IndicatorChips'
import IndicatorDialog from './IndicatorDialog'
import SetupCard from './SetupCard'
import SourceFooter from './SourceFooter'
import { CHART_TYPES } from '../utils/chartTypes'

const RANGES = ['1M', '3M', '6M', '1Y', '5Y', 'MAX']
const INTERVALS = ['15m', '1H', '1D', '1W']
const ALLOWED = { '15m': ['1M'], '1H': ['1M', '3M', '6M', '1Y'], '1D': RANGES, '1W': RANGES }

const BULL = '#22c07a'
const BEAR = '#ef5350'
const BRASS = '#e8b64c'
const ANALYZE_STEPS = ['Reading the chart…', 'Marking the levels…', 'Building the plan…', 'Writing the narration…']
const STORE_KEY = 'sl_active_indicators'

let uidCounter = 0
const newUid = () => `i${Date.now().toString(36)}${++uidCounter}`

const loadSaved = () => {
  try { return JSON.parse(localStorage.getItem(STORE_KEY)) || [] } catch { return [] }
}

export default function CandleChart({ symbol, analyzeSignal = 0, onAnalysis, watched, onToggleWatch }) {
  const containerRef = useRef(null)
  const overlayRef = useRef(null)
  const chartRef = useRef(null)
  const mainSeriesRef = useRef(null)
  const volumeSeriesRef = useRef(null)
  const markersApiRef = useRef(null)
  const priceLinesRef = useRef([])
  const indicatorHandlesRef = useRef([]) // flat list of series handles to clear
  const analysisRef = useRef(null)
  const candlesRef = useRef([])

  const [chartType, setChartType] = useState('candles')
  const [typeMenuOpen, setTypeMenuOpen] = useState(false)
  const [range, setRange] = useState('1Y')
  const [interval, setInterval_] = useState('1D')
  const [meta, setMeta] = useState(null)
  const [source, setSource] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [analysis, setAnalysis] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeStep, setAnalyzeStep] = useState(0)
  const [analyzeError, setAnalyzeError] = useState('')
  const [legend, setLegend] = useState(null)
  const [alertOpen, setAlertOpen] = useState(false)
  const [alertPrice, setAlertPrice] = useState('')
  const [alertMsg, setAlertMsg] = useState('')

  const createAlert = async () => {
    const p = parseFloat(alertPrice)
    if (!p || !meta) return
    const direction = p >= meta.last_close ? 'above' : 'below'
    try {
      await api.createAlert(symbol, p, direction)
      setAlertMsg(`Alert set: ${direction} ${p}`)
      setTimeout(() => { setAlertMsg(''); setAlertOpen(false) }, 1400)
    } catch (e) { setAlertMsg(e.message) }
  }
  const [dialogOpen, setDialogOpen] = useState(false)
  const [activeInds, setActiveInds] = useState(loadSaved) // [{uid,id,params,label,paramSpec}]
  const [indResults, setIndResults] = useState({})        // uid -> compute result

  // ---------------------------------------------------------- overlay (svg)
  const redrawOverlay = () => {
    const svg = overlayRef.current
    const chart = chartRef.current
    const series = mainSeriesRef.current
    if (!svg || !chart || !series) return
    const a = analysisRef.current
    if (!a) { svg.innerHTML = ''; return }
    const width = svg.clientWidth
    const ts = chart.timeScale()
    const y = (price) => series.priceToCoordinate(price)
    const parts = []
    for (const z of a.zones || []) {
      const yTop = y(z.price_high)
      const yBot = y(z.price_low)
      if (yTop == null || yBot == null) continue
      const color = z.kind === 'support' ? '34,192,122' : '239,83,80'
      parts.push(
        `<rect x="0" y="${Math.min(yTop, yBot)}" width="${width}" height="${Math.max(Math.abs(yBot - yTop), 2)}" fill="rgba(${color},0.09)" stroke="rgba(${color},0.35)" stroke-dasharray="5 4" stroke-width="1"/>`,
        `<text x="8" y="${Math.min(yTop, yBot) + 13}" fill="rgba(${color},0.9)" font-size="10" font-family="JetBrains Mono, monospace">${z.kind.toUpperCase()} × ${z.touches}</text>`
      )
    }
    const visible = ts.getVisibleRange?.()
    for (const l of a.trendlines || []) {
      let { time1, price1, time2, price2 } = l
      if (visible && time2 !== time1) {
        const slope = (price2 - price1) / (time2 - time1)
        if (time1 < visible.from) { price1 += slope * (visible.from - time1); time1 = visible.from }
        if (time2 > visible.to) { price2 -= slope * (time2 - visible.to); time2 = visible.to }
      }
      const x1 = ts.timeToCoordinate(time1)
      const x2 = ts.timeToCoordinate(time2)
      const y1 = y(price1)
      const y2 = y(price2)
      if ([x1, x2, y1, y2].some((v) => v == null)) continue
      parts.push(`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${l.direction === 'up' ? BULL : BEAR}" stroke-width="1.5" stroke-dasharray="2 3" opacity="0.85"/>`)
    }
    svg.innerHTML = parts.join('')
  }

  // ---------------------------------------------------------- chart create
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const chart = createChart(el, {
      autoSize: true,
      // Let the PAGE scroll over the chart: the wheel was hijacking page
      // scroll (felt like "can't scroll up/down" on the chart view).
      // Zoom still works via pinch, scale-axis drag, and double-click reset.
      handleScroll: { mouseWheel: false, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { mouseWheel: false, pinch: true, axisPressedMouseMove: true, axisDoubleClickReset: true },
      layout: {
        background: { color: 'transparent' }, textColor: '#8b9bb4',
        fontFamily: "'JetBrains Mono', ui-monospace, monospace", fontSize: 11,
        panes: { separatorColor: '#1a2740', separatorHoverColor: '#e8b64c55', enableResize: true },
      },
      grid: { vertLines: { color: 'rgba(36,51,79,0.35)' }, horzLines: { color: 'rgba(36,51,79,0.35)' } },
      crosshair: {
        vertLine: { color: '#e8b64c55', labelBackgroundColor: '#1a2740' },
        horzLine: { color: '#e8b64c55', labelBackgroundColor: '#1a2740' },
      },
      rightPriceScale: { borderColor: 'rgba(36,51,79,0.8)' },
      timeScale: { borderColor: 'rgba(36,51,79,0.8)', timeVisible: true },
    })
    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' }, priceScaleId: 'vol',
      priceLineVisible: false, lastValueVisible: false,
    })
    chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    chartRef.current = chart
    volumeSeriesRef.current = volume

    const redraw = () => redrawOverlay()
    chart.timeScale().subscribeVisibleTimeRangeChange(redraw)
    chart.subscribeCrosshairMove((param) => {
      const s = mainSeriesRef.current
      if (!param?.time || !s) { setLegend(null); return }
      const d = param.seriesData.get(s)
      if (!d) { setLegend(null); return }
      const vol = volumeSeriesRef.current ? param.seriesData.get(volumeSeriesRef.current)?.value : null
      setLegend({ ...d, vol })
    })
    const ro = new ResizeObserver(redraw)
    ro.observe(el)
    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
      mainSeriesRef.current = null
      volumeSeriesRef.current = null
      markersApiRef.current = null
    }
  }, [])

  // ------------------------------------------------- main series per type
  const applyAnnotationsToMain = () => {
    const series = mainSeriesRef.current
    const a = analysisRef.current
    priceLinesRef.current = []
    if (!series) return
    try { markersApiRef.current = createSeriesMarkers(series, []) } catch { markersApiRef.current = null }
    if (!a) return
    if (a.setup?.plan) {
      const p = a.setup.plan
      const mk = (price, color, title, style = LineStyle.Solid) =>
        series.createPriceLine({ price, color, title, lineWidth: 1, lineStyle: style, axisLabelVisible: true })
      priceLinesRef.current = [
        mk(p.entry_high, BULL, 'ENTRY'), mk(p.stop_loss, BEAR, 'STOP'),
        mk(p.target1, BRASS, 'T1', LineStyle.Dashed), mk(p.target2, BRASS, 'T2', LineStyle.Dashed),
      ]
    }
    markersApiRef.current?.setMarkers?.(
      (a.markers || []).map((m) => ({ time: m.time, position: m.position, shape: m.shape, text: m.label, color: BRASS }))
    )
  }

  const rebuildMainSeries = () => {
    const chart = chartRef.current
    if (!chart) return
    const def = CHART_TYPES[chartType] || CHART_TYPES.candles
    if (mainSeriesRef.current) {
      try { chart.removeSeries(mainSeriesRef.current) } catch { /* gone */ }
      mainSeriesRef.current = null
    }
    const data = def.transform(candlesRef.current)
    const options = def.optionsFrom ? def.optionsFrom(data) : def.options
    const series = chart.addSeries(def.kind, options, 0)
    series.setData(data)
    mainSeriesRef.current = series
    applyAnnotationsToMain()
    redrawOverlay()
  }

  useEffect(() => {
    if (candlesRef.current.length) rebuildMainSeries()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartType])

  // ------------------------------------------------------------ data load
  useEffect(() => {
    if (!symbol) return
    let cancelled = false
    setLoading(true)
    setError('')
    clearAnalysis()
    api.candles(symbol, range, interval)
      .then((data) => {
        if (cancelled || !chartRef.current) return
        candlesRef.current = data.candles
        rebuildMainSeries()
        volumeSeriesRef.current.setData(
          data.candles.map((c) => ({
            time: c.time, value: c.volume,
            color: c.close >= c.open ? 'rgba(34,192,122,0.35)' : 'rgba(239,83,80,0.32)',
          }))
        )
        chartRef.current.timeScale().fitContent()
        setMeta(data.meta)
        setSource(data.source)
        if (data.range !== range) setRange(data.range)
      })
      .catch((err) => { if (!cancelled) { setError(err.message); setMeta(null); setSource(null) } })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, range, interval])

  // ------------------------------------------------------------ indicators
  useEffect(() => {
    localStorage.setItem(STORE_KEY, JSON.stringify(
      activeInds.map(({ uid, id, params, label, paramSpec }) => ({ uid, id, params, label, paramSpec }))
    ))
    if (activeInds.length === 0) { setIndResults({}); return }
    let cancelled = false
    api.computeIndicators(symbol, range, interval,
      activeInds.map(({ uid, id, params }) => ({ uid, id, params })))
      .then((res) => {
        if (cancelled) return
        const map = {}
        for (const r of res.results) map[r.uid] = r
        setIndResults(map)
      })
      .catch(() => { if (!cancelled) setIndResults({}) })
    return () => { cancelled = true }
  }, [activeInds, symbol, range, interval])

  // draw indicator series whenever results change
  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    for (const h of indicatorHandlesRef.current) {
      try { chart.removeSeries(h) } catch { /* gone */ }
    }
    indicatorHandlesRef.current = []
    let nextPane = 1
    for (const inst of activeInds) {
      const result = indResults[inst.uid]
      if (!result) continue
      const paneIndex = result.pane === 'overlay' ? 0 : nextPane++
      let first = null
      for (const s of result.series) {
        const handle = s.type === 'histogram'
          ? chart.addSeries(HistogramSeries, { color: s.color, priceLineVisible: false, lastValueVisible: false }, paneIndex)
          : chart.addSeries(LineSeries, {
              color: s.color, lineWidth: s.lineWidth || 1, lineStyle: s.lineStyle || 0,
              priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
            }, paneIndex)
        handle.setData(s.data)
        indicatorHandlesRef.current.push(handle)
        if (!first) first = handle
      }
      if (first && result.pane === 'sub') {
        for (const ref of result.reference_lines || []) {
          first.createPriceLine({ price: ref, color: '#8b9bb455', lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: false, title: '' })
        }
        try { chart.panes()[paneIndex]?.setHeight(110) } catch { /* pane sizing optional */ }
      }
    }
  }, [indResults, activeInds])

  const addIndicator = (catalogEntry) => {
    const params = {}
    for (const [name, spec] of Object.entries(catalogEntry.params || {})) params[name] = spec.default
    const label = catalogEntry.name
    setActiveInds((a) => [...a, { uid: newUid(), id: catalogEntry.id, params, label, paramSpec: catalogEntry.params || {} }])
  }
  const updateParams = (uid, params) =>
    setActiveInds((a) => a.map((i) => (i.uid === uid ? { ...i, params } : i)))
  const removeIndicator = (uid) =>
    setActiveInds((a) => a.filter((i) => i.uid !== uid))

  // --------------------------------------------------------------- analyze
  const clearAnalysis = () => {
    analysisRef.current = null
    setAnalysis(null)
    onAnalysis?.(null)
    setAnalyzeError('')
    for (const line of priceLinesRef.current) {
      try { mainSeriesRef.current?.removePriceLine(line) } catch { /* gone */ }
    }
    priceLinesRef.current = []
    markersApiRef.current?.setMarkers?.([])
    redrawOverlay()
  }

  const runAnalyze = async () => {
    if (analyzing) return
    clearAnalysis()
    setAnalyzing(true)
    setAnalyzeStep(0)
    const stepper = window.setInterval(() => setAnalyzeStep((s) => Math.min(s + 1, ANALYZE_STEPS.length - 1)), 2500)
    try {
      const result = await api.analyze(symbol, range, interval)
      analysisRef.current = result
      setAnalysis(result)
      onAnalysis?.(result)
      applyAnnotationsToMain()
      redrawOverlay()
    } catch (err) {
      setAnalyzeError(err.message)
    } finally {
      window.clearInterval(stepper)
      setAnalyzing(false)
    }
  }

  useEffect(() => {
    if (analyzeSignal > 0) runAnalyze()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analyzeSignal])

  const pickInterval = (iv) => {
    setInterval_(iv)
    if (!ALLOWED[iv].includes(range)) setRange(ALLOWED[iv][ALLOWED[iv].length - 1])
  }

  const up = meta ? meta.change >= 0 : true
  const currencySign = meta?.currency === 'INR' ? '₹' : meta?.currency === 'USD' ? '$' : ''
  const typeDef = CHART_TYPES[chartType]

  return (
    <div>
      <section className="bg-ink-900 border border-ink-700 rounded-xl p-4 sm:p-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="flex items-center gap-1.5">
              <h2 className="font-[family-name:var(--font-display)] text-mist-50 text-lg font-semibold tracking-tight">{symbol}</h2>
              <button onClick={() => onToggleWatch?.(symbol)} title={watched ? 'Remove from watchlist' : 'Add to watchlist'}
                      className={`text-lg leading-none ${watched ? 'text-brass-400' : 'text-mist-400/50 hover:text-brass-400'}`}>
                {watched ? '★' : '☆'}
              </button>
              <div className="relative">
                <button onClick={() => { setAlertOpen(!alertOpen); setAlertPrice(meta ? String(meta.last_close) : '') }}
                        title="Set price alert" className="text-sm text-mist-400/70 hover:text-brass-400 leading-none">🔔+</button>
                {alertOpen && (
                  <div className="rise-in absolute z-40 top-7 left-0 bg-ink-900 border border-ink-600 rounded-lg p-3 shadow-xl shadow-black/50 w-52">
                    <span className="text-[10px] uppercase tracking-wider text-mist-400">Alert me at price</span>
                    <input type="number" step="any" value={alertPrice} onChange={(e) => setAlertPrice(e.target.value)}
                           className="mt-1 w-full bg-ink-800 border border-ink-600 rounded px-2 py-1.5 text-sm text-mist-50 price focus:border-brass-400 focus:outline-none" />
                    <button onClick={createAlert}
                            className="mt-2 w-full text-xs bg-brass-400 hover:bg-brass-300 text-ink-950 font-semibold rounded px-2 py-1.5">
                      Set alert
                    </button>
                    {alertMsg && <p className="text-[10px] text-brass-300 mt-1.5">{alertMsg}</p>}
                  </div>
                )}
              </div>
            </div>
            {meta && (
              <div className="flex items-baseline gap-3 mt-0.5">
                <span className="price text-2xl text-mist-50">
                  {currencySign}{meta.last_close?.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </span>
                <span className={`price text-sm px-1.5 py-0.5 rounded ${up ? 'text-bull-500 bg-bull-500/10' : 'text-bear-500 bg-bear-500/10'}`}>
                  {up ? '+' : ''}{meta.change?.toFixed(2)} ({up ? '+' : ''}{meta.change_pct?.toFixed(2)}%)
                </span>
              </div>
            )}
          </div>

          <div className="flex flex-col items-end gap-2">
            <div className="flex items-center gap-2 flex-wrap justify-end">
              {/* Chart type menu */}
              <div className="relative">
                <button onClick={() => setTypeMenuOpen((o) => !o)}
                        className="text-xs text-mist-200 bg-ink-800 hover:bg-ink-700 border border-ink-600 rounded-lg px-3 py-1.5">
                  {typeDef.label} ▾
                </button>
                {typeMenuOpen && (
                  <ul className="rise-in absolute z-40 right-0 mt-1.5 w-64 bg-ink-900 border border-ink-600 rounded-lg shadow-xl shadow-black/50 overflow-hidden max-h-80 overflow-y-auto">
                    {Object.entries(CHART_TYPES).map(([key, def]) => (
                      <li key={key}>
                        <button
                          onClick={() => { setChartType(key); setTypeMenuOpen(false) }}
                          className={`w-full text-left px-3 py-2 hover:bg-ink-800 ${key === chartType ? 'bg-ink-800' : ''}`}
                        >
                          <span className="text-xs text-mist-50">{def.label}</span>
                          <span className="block text-[10px] text-mist-400 leading-snug mt-0.5">{def.blurb}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <button onClick={() => setDialogOpen(true)}
                      className="text-xs text-mist-200 bg-ink-800 hover:bg-ink-700 border border-ink-600 rounded-lg px-3 py-1.5">
                ƒx Indicators
              </button>

              <button
                onClick={runAnalyze}
                disabled={analyzing || loading || !!error}
                className={`bg-brass-400 hover:bg-brass-300 disabled:opacity-50 text-ink-950 font-semibold text-sm rounded-lg px-4 py-1.5 transition-colors ${analyzing ? 'analyzing' : ''}`}
              >
                {analyzing ? ANALYZE_STEPS[analyzeStep] : 'Analyze'}
              </button>

              <div className="flex rounded-lg border border-ink-600 overflow-hidden">
                {INTERVALS.map((iv) => (
                  <button key={iv} onClick={() => pickInterval(iv)}
                          className={`px-3 py-1.5 text-xs price transition-colors ${
                            interval === iv ? 'bg-brass-400 text-ink-950 font-semibold' : 'text-mist-400 hover:text-mist-50 hover:bg-ink-800'
                          }`}>
                    {iv}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex rounded-lg border border-ink-600 overflow-hidden">
              {RANGES.map((r) => {
                const allowed = ALLOWED[interval].includes(r)
                return (
                  <button key={r} onClick={() => allowed && setRange(r)} disabled={!allowed}
                          title={allowed ? '' : `Not available on ${interval} candles (data provider limit)`}
                          className={`px-3 py-1.5 text-xs price transition-colors ${
                            range === r ? 'bg-ink-600 text-mist-50 font-semibold'
                            : allowed ? 'text-mist-400 hover:text-mist-50 hover:bg-ink-800'
                            : 'text-mist-400/30 cursor-not-allowed'
                          }`}>
                    {r}
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        <IndicatorChips active={activeInds} onUpdateParams={updateParams} onRemove={removeIndicator} />

        <div className="relative mt-4">
          <div ref={containerRef} className="h-[520px] w-full" />
          <svg ref={overlayRef} className="absolute inset-0 w-full h-[520px] pointer-events-none" aria-hidden="true" />
          {legend && (
            <div className="absolute top-2 left-2 z-10 price text-[11px] text-mist-200 bg-ink-950/80 backdrop-blur border border-ink-700 rounded px-2.5 py-1.5 pointer-events-none">
              {legend.open != null ? (
                <>
                  O <span className="text-mist-50">{legend.open?.toFixed(2)}</span>{' '}
                  H <span className="text-bull-500">{legend.high?.toFixed(2)}</span>{' '}
                  L <span className="text-bear-500">{legend.low?.toFixed(2)}</span>{' '}
                  C <span className={legend.close >= legend.open ? 'text-bull-500' : 'text-bear-500'}>{legend.close?.toFixed(2)}</span>
                </>
              ) : (
                <>Price <span className="text-mist-50">{legend.value?.toFixed(2)}</span></>
              )}
              {legend.vol != null && <span className="text-mist-400"> · Vol {Intl.NumberFormat('en', { notation: 'compact' }).format(legend.vol)}</span>}
            </div>
          )}
          {loading && (
            <div className="absolute inset-0 grid place-items-center bg-ink-900/60 backdrop-blur-[1px] rounded-lg">
              <span className="w-6 h-6 border-2 border-mist-400/30 border-t-brass-400 rounded-full animate-spin" />
            </div>
          )}
          {error && !loading && (
            <div className="absolute inset-0 grid place-items-center">
              <p className="text-sm text-bear-500 bg-bear-500/10 border border-bear-500/30 rounded-lg px-4 py-3 max-w-md text-center">{error}</p>
            </div>
          )}
        </div>

        {chartType !== 'candles' && analysis && (
          <p className="mt-2 text-[11px] text-brass-400/90">
            Note: the Analyze engine always computes on real candles — switch back to Candles view to judge the setup precisely.
          </p>
        )}
        {analyzeError && (
          <p className="mt-3 text-sm text-bear-500 bg-bear-500/10 border border-bear-500/30 rounded-lg px-3 py-2">{analyzeError}</p>
        )}

        <SourceFooter source={source} />
      </section>

      <SetupCard analysis={analysis} currencySign={currencySign} />

      <IndicatorDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onAdd={(entry) => addIndicator(entry)}
        activeIds={activeInds.map((i) => i.id)}
      />
    </div>
  )
}
