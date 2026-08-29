// Chart-type definitions: how to render the SAME OHLCV in different views.
// Each entry: label, series kind, options, and a data transform.
import {
  AreaSeries, BarSeries, BaselineSeries, CandlestickSeries, HistogramSeries,
  LineSeries, LineType,
} from 'lightweight-charts'

const BULL = '#22c07a'
const BEAR = '#ef5350'

const ohlc = (c) => c.map(({ time, open, high, low, close }) => ({ time, open, high, low, close }))
const closes = (c) => c.map(({ time, close }) => ({ time, value: close }))

function heikinAshi(c) {
  const out = []
  let prevO = null
  let prevC = null
  for (const k of c) {
    const haClose = (k.open + k.high + k.low + k.close) / 4
    const haOpen = prevO == null ? (k.open + k.close) / 2 : (prevO + prevC) / 2
    out.push({
      time: k.time,
      open: haOpen,
      close: haClose,
      high: Math.max(k.high, haOpen, haClose),
      low: Math.min(k.low, haOpen, haClose),
    })
    prevO = haOpen
    prevC = haClose
  }
  return out
}

export const CHART_TYPES = {
  candles: {
    label: 'Candles', kind: CandlestickSeries, transform: ohlc,
    options: { upColor: BULL, downColor: BEAR, borderUpColor: BULL, borderDownColor: BEAR, wickUpColor: BULL, wickDownColor: BEAR },
    blurb: 'The default view: each candle shows open, high, low, close.',
  },
  hollow: {
    label: 'Hollow candles', kind: CandlestickSeries, transform: ohlc,
    options: { upColor: 'rgba(0,0,0,0)', downColor: BEAR, borderUpColor: BULL, borderDownColor: BEAR, wickUpColor: BULL, wickDownColor: BEAR },
    blurb: 'Up candles are hollow — some traders find trend shifts easier to spot.',
  },
  heikin: {
    label: 'Heikin Ashi', kind: CandlestickSeries, transform: heikinAshi,
    options: { upColor: BULL, downColor: BEAR, borderUpColor: BULL, borderDownColor: BEAR, wickUpColor: BULL, wickDownColor: BEAR },
    blurb: 'Averaged candles that smooth noise — long green runs = clean uptrend. Note: prices are synthetic averages, not real fills.',
  },
  bars: {
    label: 'Bars (OHLC)', kind: BarSeries, transform: ohlc,
    options: { upColor: BULL, downColor: BEAR },
    blurb: 'Classic open/close tick bars — the pre-candlestick standard.',
  },
  highlow: {
    label: 'High-Low', kind: BarSeries, transform: ohlc,
    options: { upColor: BULL, downColor: BEAR, openVisible: false },
    blurb: 'Just the range of each period — pure volatility view.',
  },
  line: {
    label: 'Line', kind: LineSeries, transform: closes,
    options: { color: '#4f9cf9', lineWidth: 2 },
    blurb: 'Closing prices only — the cleanest big-picture trend view.',
  },
  line_markers: {
    label: 'Line + markers', kind: LineSeries, transform: closes,
    options: { color: '#4f9cf9', lineWidth: 2, pointMarkersVisible: true },
    blurb: 'Line chart with a dot on every close.',
  },
  step: {
    label: 'Step line', kind: LineSeries, transform: closes,
    options: { color: '#4f9cf9', lineWidth: 2, lineType: LineType.WithSteps },
    blurb: 'Holds each close flat until the next — good for level-based thinking.',
  },
  area: {
    label: 'Area', kind: AreaSeries, transform: closes,
    options: { lineColor: '#4f9cf9', topColor: 'rgba(79,156,249,0.35)', bottomColor: 'rgba(79,156,249,0.02)', lineWidth: 2 },
    blurb: 'A filled line chart — the app-style view INDmoney opens with.',
  },
  baseline: {
    label: 'Baseline', kind: BaselineSeries, transform: closes,
    optionsFrom: (data) => ({
      baseValue: { type: 'price', price: data.length ? data[0].value : 0 },
      topLineColor: BULL, topFillColor1: 'rgba(34,192,122,0.28)', topFillColor2: 'rgba(34,192,122,0.03)',
      bottomLineColor: BEAR, bottomFillColor1: 'rgba(239,83,80,0.03)', bottomFillColor2: 'rgba(239,83,80,0.28)',
    }),
    blurb: 'Green above / red below your anchor price — instant profit-or-loss view.',
  },
  columns: {
    label: 'Columns', kind: HistogramSeries,
    transform: (c) => c.map((k) => ({ time: k.time, value: k.close, color: k.close >= k.open ? 'rgba(34,192,122,0.6)' : 'rgba(239,83,80,0.6)' })),
    options: {},
    blurb: 'Closing price as colored columns.',
  },
}
