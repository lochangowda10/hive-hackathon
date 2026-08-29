import { useEffect, useState } from 'react'
import { useAuth } from '../auth'

// Deterministic ambient candle field for the brand panel
const BARS = Array.from({ length: 26 }, (_, i) => ({
  h: 28 + ((i * 37) % 52),
  up: (i * 7) % 3 !== 0,
  delay: (i % 9) * 0.45,
}))

export default function Login() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ username: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [demo, setDemo] = useState(false)
  const [backendDown, setBackendDown] = useState(false)

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((d) => { setDemo(!!d.demo); setBackendDown(false) })
      .catch(() => setBackendDown(true))
  }, [])

  const tryDemo = async () => {
    setError('')
    setBusy(true)
    try { await login('demo@swinglens.app', 'swingdemo123') }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (mode === 'login') await login(form.email, form.password)
      else await register(form.username, form.email, form.password)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-full flex">
      {/* Brand panel */}
      <div className="hidden lg:flex flex-col justify-between w-[46%] bg-ink-900 border-r border-ink-700 p-12 relative overflow-hidden">
        <div>
          <div className="flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-brass-400 flex items-center justify-center font-[family-name:var(--font-display)] font-bold text-ink-950 text-lg">S</span>
            <span className="font-[family-name:var(--font-display)] text-mist-50 text-xl font-semibold tracking-tight">SwingLens</span>
          </div>
          <h1 className="mt-16 font-[family-name:var(--font-display)] text-mist-50 text-5xl leading-[1.08] font-semibold max-w-md">
            See the trade<br />before you take it.
          </h1>
          <p className="mt-6 text-mist-400 max-w-sm leading-relaxed">
            Charts annotated like an analyst drew them. Every number traced to its source. Nothing invented.
          </p>
        </div>

        {/* Ambient candle field */}
        <div className="flex items-end gap-2 h-40" aria-hidden="true">
          {BARS.map((b, i) => (
            <div
              key={i}
              className={`candle-bar w-2 rounded-sm ${b.up ? 'bg-bull-500/60' : 'bg-bear-500/50'}`}
              style={{ height: `${b.h}%`, animationDelay: `${b.delay}s` }}
            />
          ))}
        </div>
      </div>

      {/* Form panel */}
      <div className="flex-1 flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-3 mb-10">
            <span className="w-9 h-9 rounded-lg bg-brass-400 flex items-center justify-center font-[family-name:var(--font-display)] font-bold text-ink-950 text-lg">S</span>
            <span className="font-[family-name:var(--font-display)] text-mist-50 text-xl font-semibold">SwingLens</span>
          </div>

          {backendDown && (
            <div className="mb-5 text-xs text-brass-300 bg-brass-400/10 border border-brass-400/40 rounded-lg px-3 py-2.5 leading-relaxed">
              <strong>Backend not reachable.</strong> Start it in another terminal:
              <code className="price block mt-1 text-brass-400">cd backend → venv\Scripts\activate → pip install -r requirements.txt → uvicorn app.main:app --reload --port 8000</code>
              (New phases add new Python packages — the pip install line matters after every upgrade.)
            </div>
          )}
          <h2 className="font-[family-name:var(--font-display)] text-mist-50 text-2xl font-semibold">
            {mode === 'login' ? 'Welcome back' : 'Create your account'}
          </h2>
          <p className="text-mist-400 text-sm mt-1">
            {mode === 'login' ? 'Sign in to open your workspace.' : 'Local account, stored on this machine.'}
          </p>

          {mode === 'register' && (
            <label className="block mt-6">
              <span className="text-xs uppercase tracking-wider text-mist-400">Username</span>
              <input
                value={form.username} onChange={set('username')} required minLength={3}
                className="mt-1.5 w-full bg-ink-800 border border-ink-600 rounded-lg px-3.5 py-2.5 text-mist-50 placeholder-mist-400/50 focus:border-brass-400 focus:outline-none"
                placeholder="trader_one"
              />
            </label>
          )}

          <label className="block mt-5">
            <span className="text-xs uppercase tracking-wider text-mist-400">Email</span>
            <input
              type="email" value={form.email} onChange={set('email')} required
              className="mt-1.5 w-full bg-ink-800 border border-ink-600 rounded-lg px-3.5 py-2.5 text-mist-50 placeholder-mist-400/50 focus:border-brass-400 focus:outline-none"
              placeholder="you@example.com"
            />
          </label>

          <label className="block mt-5">
            <span className="text-xs uppercase tracking-wider text-mist-400">Password</span>
            <input
              type="password" value={form.password} onChange={set('password')} required minLength={8}
              className="mt-1.5 w-full bg-ink-800 border border-ink-600 rounded-lg px-3.5 py-2.5 text-mist-50 placeholder-mist-400/50 focus:border-brass-400 focus:outline-none"
              placeholder="At least 8 characters"
            />
          </label>

          {error && (
            <p className="mt-4 text-sm text-bear-500 bg-bear-500/10 border border-bear-500/30 rounded-lg px-3 py-2">{error}</p>
          )}

          <button
            disabled={busy}
            className="mt-6 w-full bg-brass-400 hover:bg-brass-300 disabled:opacity-60 text-ink-950 font-semibold rounded-lg py-2.5 transition-colors"
          >
            {busy ? 'One moment…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>

          {demo && (
            <button
              type="button"
              onClick={tryDemo}
              disabled={busy}
              className="mt-3 w-full border border-brass-400/50 text-brass-400 hover:bg-brass-400/10 disabled:opacity-60 font-medium rounded-lg py-2.5 transition-colors"
            >
              ✨ Try the demo account
            </button>
          )}

          <button
            type="button"
            onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}
            className="mt-4 w-full text-sm text-mist-400 hover:text-mist-200"
          >
            {mode === 'login' ? "New here? Create an account" : 'Already registered? Sign in'}
          </button>

          <p className="mt-8 text-[10px] text-mist-400/60 leading-relaxed">
            SwingLens is a research and education tool — not investment advice, and not a
            SEBI-registered advisory. The engine shows what the data says with full sourcing;
            you make the call. It never executes trades. Verify anything important at the
            linked sources before acting.
          </p>
        </form>
      </div>
    </div>
  )
}
