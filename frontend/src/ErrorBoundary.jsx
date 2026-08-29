import { Component } from 'react'

// Any runtime crash renders THIS instead of a blank page - the single most
// valuable debugging feature a local-first app can have.
export default class ErrorBoundary extends Component {
  state = { error: null }
  static getDerivedStateFromError(error) { return { error } }
  render() {
    if (!this.state.error) return this.props.children
    const details = `${this.state.error?.message || this.state.error}\n\n${this.state.error?.stack || ''}`
    return (
      <div className="min-h-full grid place-items-center p-6">
        <div className="max-w-xl w-full bg-ink-900 border border-bear-500/40 rounded-xl p-5">
          <h1 className="font-[family-name:var(--font-display)] text-mist-50 font-semibold">
            Something crashed — but you can see it now
          </h1>
          <p className="text-xs text-mist-400 mt-1">
            Copy this and paste it to your AI builder; it's everything needed to fix it.
          </p>
          <pre className="mt-3 text-[11px] text-bear-500 bg-ink-950 border border-ink-700 rounded-lg p-3 overflow-auto max-h-64 whitespace-pre-wrap">{details}</pre>
          <div className="flex gap-2 mt-3">
            <button onClick={() => navigator.clipboard?.writeText(details)}
                    className="text-xs bg-brass-400 hover:bg-brass-300 text-ink-950 font-semibold rounded-lg px-3 py-1.5">
              Copy details
            </button>
            <button onClick={() => location.reload()}
                    className="text-xs text-mist-400 hover:text-mist-50 border border-ink-600 rounded-lg px-3 py-1.5">
              Reload app
            </button>
          </div>
        </div>
      </div>
    )
  }
}
