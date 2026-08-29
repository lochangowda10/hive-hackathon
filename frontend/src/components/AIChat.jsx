import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

// ---------- markdown-lite (no deps): **bold**, `code`, bullets, ### heads
function Rich({ text }) {
  const inline = (s, k) =>
    s.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) =>
      part.startsWith('**') ? <strong key={`${k}-${i}`} className="text-mist-50">{part.slice(2, -2)}</strong>
      : part.startsWith('`') ? <code key={`${k}-${i}`} className="price text-brass-300 bg-ink-900/70 rounded px-1">{part.slice(1, -1)}</code>
      : part
    )
  const blocks = []
  let list = null
  text.split('\n').forEach((line) => {
    if (/^\s*[-*]\s+/.test(line)) {
      if (!list) { list = []; blocks.push(list) }
      list.push(line.replace(/^\s*[-*]\s+/, ''))
    } else { list = null; blocks.push(line) }
  })
  return (
    <>
      {blocks.map((b, i) =>
        Array.isArray(b) ? (
          <ul key={i} className="list-disc pl-4 my-1 space-y-0.5">{b.map((li, j) => <li key={j}>{inline(li, `${i}-${j}`)}</li>)}</ul>
        ) : /^###\s+/.test(b) ? (
          <p key={i} className="text-[11px] uppercase tracking-wider text-brass-400 mt-2">{b.replace(/^###\s+/, '')}</p>
        ) : b.trim() === '' ? null : <p key={i} className="my-1">{inline(b, i)}</p>
      )}
    </>
  )
}

// ---------- computed scan results card (engine output, never LLM-picked)
function ScanCard({ scan, onOpenSymbol, onAnalyze }) {
  const [showTech, setShowTech] = useState(false)
  const Row = ({ r, actionable }) => (
    <div className="flex items-center gap-2 bg-ink-900/60 border border-ink-700/70 rounded-lg px-2.5 py-2">
      <div className="min-w-0 flex-1">
        <span className="text-xs text-mist-50">{r.name}</span>
        <span className="price text-[10px] text-mist-400 ml-1.5">{r.symbol}</span>
        <span className="block text-[10px] text-mist-400 uppercase tracking-wider">{r.state.replaceAll('_', ' ')}</span>
      </div>
      {actionable && r.plan && (
        <span className="price text-[10px] text-mist-400 shrink-0 text-right hidden sm:block">
          E {r.plan.entry_low}–{r.plan.entry_high}<br />RR {r.plan.risk_reward}:1
        </span>
      )}
      <span className={`price text-xs shrink-0 ${r.confidence >= 60 ? 'text-bull-500' : 'text-brass-400'}`}>
        {actionable ? `${r.confidence}` : `RSI ${r.rsi ?? '—'}`}
      </span>
      <button onClick={() => (actionable ? onAnalyze(r.symbol) : onOpenSymbol(r.symbol))}
              className="shrink-0 text-[10px] bg-brass-400 hover:bg-brass-300 text-ink-950 font-semibold rounded px-2 py-1">
        {actionable ? 'Analyze' : 'Open'}
      </button>
    </div>
  )
  return (
    <div className="bg-ink-800 border border-ink-600 rounded-lg px-3 py-2.5 mr-2 rise-in">
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className="text-xs font-semibold text-mist-50">Engine scan · {scan.universe}</span>
        <span className="text-[10px] text-mist-400">{scan.scanned} scanned in {(scan.duration_ms / 1000).toFixed(1)}s{scan.failed ? ` · ${scan.failed} skipped` : ''}</span>
      </div>
      {scan.actionable.length > 0 ? (
        <>
          <p className="text-[10px] uppercase tracking-wider text-bull-500 mt-2 mb-1">Actionable setups (ranked by confidence)</p>
          <div className="space-y-1.5">{scan.actionable.map((r) => <Row key={r.symbol} r={r} actionable />)}</div>
        </>
      ) : (
        <p className="text-xs text-mist-400 mt-2">No qualifying setups right now — the honest answer. Check the watchlist below.</p>
      )}
      {scan.watchlist.length > 0 && (
        <>
          <p className="text-[10px] uppercase tracking-wider text-brass-400 mt-2.5 mb-1">Watchlist (strong trends, waiting for entries)</p>
          <div className="space-y-1.5">{scan.watchlist.map((r) => <Row key={r.symbol} r={r} />)}</div>
        </>
      )}
      <button onClick={() => setShowTech(!showTech)} className="text-[10px] text-mist-400 hover:text-brass-400 mt-2.5">
        {showTech ? '▾' : '▸'} Techniques applied ({scan.techniques.length})
      </button>
      {showTech && (
        <ul className="mt-1 space-y-0.5">
          {scan.techniques.map((t, i) => <li key={i} className="text-[10px] text-mist-400">✓ {t}</li>)}
        </ul>
      )}
      <p className="text-[9px] text-mist-400/60 mt-2">{scan.source?.note}</p>
    </div>
  )
}

const SUGGESTIONS = [
  { label: '🔍 Scan the market for bullish setups', msg: 'scan the market for bullish swing setups' },
  { label: '⚡ Analyse this chart', msg: 'analyse this stock for a swing trade' },
  { label: '📰 What does the news say?', msg: 'What do the latest headlines say about this stock? Which are confirmed?' },
  { label: '🎓 Teach me buy-the-dip properly', msg: 'Teach me the buy-the-dip strategy properly, with the risks beginners miss' },
]

export default function AIChat({ onAnalyze, onOpenSymbol, context }) {
  const [status, setStatus] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [full, setFull] = useState(false)
  const [convId, setConvId] = useState(null)
  const [convs, setConvs] = useState([])
  const [showHistory, setShowHistory] = useState(false)
  const [lastScan, setLastScan] = useState(null)
  const [copied, setCopied] = useState(null)
  const endRef = useRef(null)

  useEffect(() => { api.aiStatus().then(setStatus).catch(() => setStatus({ online: false })) }, [])
  useEffect(() => { api.aiConversations().then(setConvs).catch(() => {}) }, [convId])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, busy])
  useEffect(() => {
    const esc = (e) => e.key === 'Escape' && setFull(false)
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [])

  // Lock page scroll while chat is fullscreen (modal hygiene)
  useEffect(() => {
    document.body.style.overflow = full ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [full])

  const newChat = () => { setConvId(null); setMessages([]); setLastScan(null); setShowHistory(false) }

  const openConversation = async (id) => {
    try {
      const msgs = await api.aiMessages(id)
      setConvId(id)
      setMessages(msgs.map((m) => (m.role === 'scan'
        ? { role: 'scan', scan: JSON.parse(m.content) }
        : { role: m.role, text: m.content })))
      setShowHistory(false)
    } catch { /* stay */ }
  }

  const removeConversation = async (id, e) => {
    e.stopPropagation()
    try { await api.aiDeleteConversation(id) } catch { /* gone */ }
    setConvs((c) => c.filter((x) => x.id !== id))
    if (id === convId) newChat()
  }

  const trimmedScan = (s) => s && {
    universe: s.universe, as_of: s.as_of,
    actionable: s.actionable, watchlist: s.watchlist,
  }

  const send = async (text) => {
    text = (text || '').trim()
    if (!text || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text }])
    setBusy(true)
    try {
      const ctx = { ...context, last_scan: trimmedScan(lastScan) }
      const res = await api.aiChat(text, ctx, convId)
      if (res.conversation_id) setConvId(res.conversation_id)
      setMessages((m) => [...m, { role: 'ai', text: res.reply }])
      if (res.action?.type === 'analyze') onAnalyze?.(res.action.symbol)
      if (res.action?.type === 'scan') {
        const scan = await api.runScan(res.action.segment)
        setLastScan(scan)
        setMessages((m) => [...m, { role: 'scan', scan }])
      }
    } catch (err) {
      setMessages((m) => [...m, { role: 'error', text: err.message }])
    } finally {
      setBusy(false)
    }
  }

  const regenerate = () => {
    const lastUser = [...messages].reverse().find((m) => m.role === 'user')
    if (lastUser) send(lastUser.text)
  }

  const copy = async (text, i) => {
    try { await navigator.clipboard.writeText(text); setCopied(i); setTimeout(() => setCopied(null), 1200) } catch { /* no clipboard */ }
  }

  const online = status?.online && (status?.model_installed ?? true)

  return (
    <aside className={full
      ? 'fixed inset-0 z-50 bg-ink-950 flex'
      : 'flex flex-col bg-ink-900 border border-ink-700 rounded-xl overflow-hidden min-h-[420px] max-h-[560px]'}>

      {/* Fullscreen history sidebar */}
      {full && (
        <div className="w-64 shrink-0 border-r border-ink-700 bg-ink-900 flex flex-col">
          <div className="p-3">
            <button onClick={newChat} className="w-full text-sm bg-brass-400 hover:bg-brass-300 text-ink-950 font-semibold rounded-lg py-2">＋ New chat</button>
          </div>
          <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-0.5">
            {convs.map((c) => (
              <button key={c.id} onClick={() => openConversation(c.id)}
                      className={`group w-full flex items-center gap-1.5 text-left text-xs rounded-lg px-2.5 py-2 ${c.id === convId ? 'bg-ink-700 text-mist-50' : 'text-mist-400 hover:bg-ink-800 hover:text-mist-200'}`}>
                <span className="flex-1 truncate">{c.title}</span>
                <span onClick={(e) => removeConversation(c.id, e)} className="opacity-0 group-hover:opacity-100 text-mist-400 hover:text-bear-500 px-1">×</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0">
        <header className="flex items-center gap-2 px-4 py-3 border-b border-ink-700 shrink-0">
          <span className={`w-2 h-2 rounded-full ${online ? 'bg-bull-500' : 'bg-bear-500'}`} />
          <h3 className="font-[family-name:var(--font-display)] text-sm font-semibold text-mist-50">SwingLens AI</h3>
          {context?.symbol && (
            <span className="price text-[10px] text-brass-400 border border-brass-400/30 rounded px-1.5 py-0.5 truncate">
              sees {context.symbol}{context.analysis ? ' + analysis' : ''}{context.news_titles?.length ? ' + news' : ''}{lastScan ? ' + scan' : ''}
            </span>
          )}
          <span className="ml-auto flex items-center gap-1">
            {!full && (
              <button onClick={() => { setShowHistory(!showHistory); api.aiConversations().then(setConvs).catch(() => {}) }}
                      title="History" className="text-mist-400 hover:text-mist-50 px-1.5 text-sm">🕘</button>
            )}
            <button onClick={newChat} title="New chat" className="text-mist-400 hover:text-mist-50 px-1.5 text-sm">＋</button>
            <button onClick={() => setFull(!full)} title={full ? 'Exit fullscreen (Esc)' : 'Fullscreen'}
                    className="text-mist-400 hover:text-mist-50 px-1.5 text-sm">{full ? '🗕' : '⛶'}</button>
          </span>
        </header>

        {/* Compact-mode history dropdown */}
        {!full && showHistory && (
          <div className="rise-in border-b border-ink-700 max-h-40 overflow-y-auto px-2 py-2 space-y-0.5 shrink-0">
            {convs.length === 0 && <p className="text-xs text-mist-400 px-2">No past chats yet.</p>}
            {convs.map((c) => (
              <button key={c.id} onClick={() => openConversation(c.id)}
                      className="group w-full flex items-center gap-1.5 text-left text-xs rounded-lg px-2.5 py-1.5 text-mist-400 hover:bg-ink-800 hover:text-mist-200">
                <span className="flex-1 truncate">{c.title}</span>
                <span onClick={(e) => removeConversation(c.id, e)} className="opacity-0 group-hover:opacity-100 hover:text-bear-500 px-1">×</span>
              </button>
            ))}
          </div>
        )}

        <div className={`flex-1 overflow-y-auto px-4 py-3 space-y-3 ${full ? 'max-w-3xl w-full mx-auto' : ''}`}>
          {!status ? <p className="text-xs text-mist-400">Checking Ollama…</p>
          : !online ? (
            <div className="text-xs text-mist-400 leading-relaxed bg-ink-800 border border-ink-600 rounded-lg p-3">
              <p className="text-mist-200 font-medium mb-1">Ollama isn't ready yet</p>
              <p>{status.detail}</p>
            </div>
          ) : messages.length === 0 ? (
            <div>
              <p className="text-xs text-mist-400 leading-relaxed mb-3">
                I can see your chart, analysis, headlines — and I can command the <strong className="text-mist-200">market scanner</strong>.
                When you want stock ideas, I never guess: the engine scans and ranks, then we discuss the results.
              </p>
              <div className="flex flex-col gap-1.5">
                {SUGGESTIONS.map((s) => (
                  <button key={s.label} onClick={() => send(s.msg)}
                          className="rise-in text-left text-xs text-mist-200 bg-ink-800 hover:bg-ink-700 border border-ink-600 hover:border-brass-400/40 rounded-lg px-3 py-2 transition-colors">
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {messages.map((m, i) => (
            m.role === 'scan' ? <ScanCard key={i} scan={m.scan} onOpenSymbol={onOpenSymbol} onAnalyze={onAnalyze} />
            : (
              <div key={i} className={`group relative text-sm leading-relaxed rounded-lg px-3 py-2 ${
                m.role === 'user' ? 'bg-ink-700 text-mist-50 ml-6'
                : m.role === 'error' ? 'bg-bear-500/10 border border-bear-500/30 text-bear-500'
                : 'bg-ink-800 text-mist-200 mr-2'
              }`}>
                {m.role === 'ai' ? <Rich text={m.text} /> : <span className="whitespace-pre-wrap">{m.text}</span>}
                {m.role === 'ai' && (
                  <span className="absolute -bottom-2 right-2 opacity-0 group-hover:opacity-100 flex gap-1">
                    <button onClick={() => copy(m.text, i)} title="Copy"
                            className="text-[10px] bg-ink-900 border border-ink-600 rounded px-1.5 py-0.5 text-mist-400 hover:text-mist-50">
                      {copied === i ? '✓ copied' : '⧉ copy'}
                    </button>
                    {i === messages.length - 1 && !busy && (
                      <button onClick={regenerate} title="Regenerate"
                              className="text-[10px] bg-ink-900 border border-ink-600 rounded px-1.5 py-0.5 text-mist-400 hover:text-mist-50">↻</button>
                    )}
                  </span>
                )}
              </div>
            )
          ))}
          {busy && (
            <div className="flex items-center gap-2 text-xs text-mist-400">
              <span className="w-3 h-3 border-2 border-mist-400/30 border-t-brass-400 rounded-full animate-spin" />
              Working on your machine…
            </div>
          )}
          <div ref={endRef} />
        </div>

        <form onSubmit={(e) => { e.preventDefault(); send(input) }}
              className={`p-3 border-t border-ink-700 flex gap-2 shrink-0 ${full ? 'max-w-3xl w-full mx-auto' : ''}`}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={online ? 'Ask anything — or "scan the market"…' : 'Start Ollama to chat'}
            disabled={!online || busy}
            className="flex-1 bg-ink-800 border border-ink-600 rounded-lg px-3 py-2 text-sm text-mist-50 placeholder-mist-400/50 focus:border-brass-400 focus:outline-none disabled:opacity-50"
          />
          <button disabled={!online || busy || !input.trim()}
                  className="bg-brass-400 hover:bg-brass-300 disabled:opacity-40 text-ink-950 font-semibold text-sm rounded-lg px-4 transition-colors">
            Send
          </button>
        </form>
      </div>
    </aside>
  )
}
