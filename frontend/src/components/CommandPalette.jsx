import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'

/**
 * Command palette (Ctrl/Cmd+K). Every item performs a real navigation or
 * real search action — no placeholders. Stock results come from the real
 * server-side search; selecting one opens its Research page.
 */
export default function CommandPalette({ open, onClose, onNavigate, onOpenSymbol }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [idx, setIdx] = useState(0)
  const timer = useRef(null)
  const inputRef = useRef(null)

  const ACTIONS = useMemo(() => [
    { id: 'pulse', label: 'Open Pulse — market news & track record', run: () => onNavigate('pulse') },
    { id: 'explore', label: 'Open Explore — market segments', run: () => onNavigate('explore') },
    { id: 'chart', label: 'Open Chart — current symbol', run: () => onNavigate('chart') },
    { id: 'research', label: 'Open AI Research — current symbol', run: () => onNavigate('research') },
    { id: 'thesis', label: 'Open Thesis Monitor', run: () => onNavigate('thesis') },
    { id: 'portfolio', label: 'Open Portfolio', run: () => onNavigate('portfolio') },
    { id: 'undervalued', label: 'Find most undervalued stocks', run: () => onNavigate('discover') },
    { id: 'discover', label: 'Open Discovery — ranked stock lists', run: () => onNavigate('discover') },
  ], [onNavigate])

  useEffect(() => {
    if (open) {
      setQ(''); setResults([]); setIdx(0)
      setTimeout(() => inputRef.current?.focus(), 30)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    clearTimeout(timer.current)
    if (q.trim().length < 2) { setResults([]); return }
    timer.current = setTimeout(() => {
      api.searchStocks(q.trim()).then((d) => setResults(d.results || [])).catch(() => {})
    }, 250)
    return () => clearTimeout(timer.current)
  }, [q, open])

  const filteredActions = useMemo(() => {
    if (!q.trim()) return ACTIONS
    const n = q.toLowerCase()
    return ACTIONS.filter((a) => a.label.toLowerCase().includes(n))
  }, [q, ACTIONS])

  const items = [
    ...results.map((r) => ({ type: 'stock', label: `${r.name} · ${r.symbol}`, sub: r.exchange || '', run: () => onOpenSymbol(r.symbol) })),
    ...filteredActions.map((a) => ({ type: 'action', ...a })),
  ]

  const choose = (item) => { item.run(); onClose() }

  const onKey = (e) => {
    if (e.key === 'Escape') onClose()
    else if (e.key === 'ArrowDown') { e.preventDefault(); setIdx((i) => Math.min(i + 1, items.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setIdx((i) => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter' && items[idx]) choose(items[idx])
  }

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 bg-ink-950/70 backdrop-blur-sm flex items-start justify-center pt-[12vh]"
         onMouseDown={onClose}>
      <div className="w-full max-w-xl bg-ink-900 border border-ink-600 rounded-xl shadow-2xl shadow-black/60 overflow-hidden"
           onMouseDown={(e) => e.stopPropagation()}>
        <input
          ref={inputRef} value={q} onChange={(e) => { setQ(e.target.value); setIdx(0) }} onKeyDown={onKey}
          placeholder="Search a stock, or type a command…  (Enter to run, Esc to close)"
          className="w-full bg-transparent px-4 py-3.5 text-sm text-mist-50 placeholder-mist-400/60 focus:outline-none border-b border-ink-700"
        />
        <ul className="max-h-80 overflow-y-auto py-1.5">
          {items.length === 0 && (
            <li className="px-4 py-6 text-center text-xs text-mist-400">
              Type 2+ letters to search stocks, or pick a command above the list.
            </li>
          )}
          {items.map((item, i) => (
            <li key={`${item.type}-${item.id || item.label}`}>
              <button
                onMouseEnter={() => setIdx(i)}
                onClick={() => choose(item)}
                className={`w-full text-left px-4 py-2.5 flex items-center gap-3 ${i === idx ? 'bg-ink-800' : ''}`}
              >
                <span className={`text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded border ${
                  item.type === 'stock' ? 'text-brass-400 border-brass-400/30' : 'text-mist-400 border-ink-600'
                }`}>{item.type === 'stock' ? 'stock' : 'go'}</span>
                <span className="text-sm text-mist-100">{item.label}</span>
                {item.sub && <span className="text-[10px] text-mist-400 ml-auto">{item.sub}</span>}
              </button>
            </li>
          ))}
        </ul>
        <div className="px-4 py-2 border-t border-ink-700 text-[10px] text-mist-400/70 flex gap-4">
          <span>↑↓ navigate</span><span>Enter run</span><span>Esc close</span>
        </div>
      </div>
    </div>
  )
}
