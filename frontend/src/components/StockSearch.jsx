import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

const badgeFor = (symbol, exchange) => {
  if (symbol?.endsWith('.NS')) return 'NSE'
  if (symbol?.endsWith('.BO')) return 'BSE'
  return exchange || 'US'
}

export default function StockSearch({ onSelect }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const boxRef = useRef(null)
  const timer = useRef(null)

  useEffect(() => {
    const close = (e) => { if (!boxRef.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const onChange = (e) => {
    const value = e.target.value
    setQ(value)
    clearTimeout(timer.current)
    if (value.trim().length < 2) { setResults([]); setOpen(false); return }
    timer.current = setTimeout(async () => {
      setLoading(true)
      try {
        const data = await api.searchStocks(value.trim())
        setResults(data.results || [])
        setOpen(true)
      } catch { setResults([]) }
      finally { setLoading(false) }
    }, 350)
  }

  const pick = (r) => {
    onSelect(r.symbol)
    setQ('')
    setResults([])
    setOpen(false)
  }

  return (
    <div ref={boxRef} className="relative w-full max-w-md">
      <div className="flex items-center bg-ink-800 border border-ink-600 rounded-lg px-3 focus-within:border-brass-400">
        <svg className="w-4 h-4 text-mist-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 10.5a6.5 6.5 0 11-13 0 6.5 6.5 0 0113 0z" />
        </svg>
        <input
          value={q}
          onChange={onChange}
          onFocus={() => results.length && setOpen(true)}
          placeholder="Search by name — Larsen & Toubro, gold, Apple…"
          className="w-full bg-transparent px-2.5 py-2 text-sm text-mist-50 placeholder-mist-400/60 focus:outline-none"
        />
        {loading && <span className="w-3.5 h-3.5 border-2 border-mist-400/40 border-t-brass-400 rounded-full animate-spin shrink-0" />}
      </div>

      {open && results.length > 0 && (
        <ul className="absolute z-30 mt-2 w-full bg-ink-900 border border-ink-600 rounded-lg shadow-xl shadow-black/50 overflow-hidden max-h-80 overflow-y-auto">
          {results.map((r) => (
            <li key={r.symbol}>
              <button
                onClick={() => pick(r)}
                className="w-full flex items-center justify-between gap-3 px-3.5 py-2.5 text-left hover:bg-ink-800"
              >
                <span className="min-w-0">
                  <span className="text-sm text-mist-50 truncate block">{r.name}</span>
                  <span className="price text-[10px] text-mist-400">{r.symbol}</span>
                </span>
                <span className="shrink-0 text-[10px] uppercase tracking-wider text-brass-400 border border-brass-400/30 rounded px-1.5 py-0.5">
                  {badgeFor(r.symbol, r.exchange)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
