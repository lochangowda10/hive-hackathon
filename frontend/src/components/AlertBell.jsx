import { useEffect, useState } from 'react'
import { api } from '../api'

export default function AlertBell({ onOpenSymbol }) {
  const [open, setOpen] = useState(false)
  const [alerts, setAlerts] = useState([])
  const [flash, setFlash] = useState(false)

  const load = () => api.alerts().then((d) => setAlerts(d.alerts || [])).catch(() => {})

  useEffect(() => {
    const check = () => api.checkAlerts()
      .then((d) => { if (d.triggered?.length) setFlash(true); load() })
      .catch(() => {})
    check()
    const t = setInterval(check, 5 * 60 * 1000)
    return () => clearInterval(t)
  }, [])

  const triggered = alerts.filter((a) => a.status === 'triggered')
  const active = alerts.filter((a) => a.status === 'active')

  return (
    <div className="relative">
      <button onClick={() => { setOpen(!open); setFlash(false); load() }} title="Price alerts"
              className="relative text-mist-400 hover:text-mist-50 px-1.5 text-lg">
        🔔
        {(triggered.length > 0 || flash) && (
          <span className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-0.5 rounded-full bg-brass-400 text-ink-950 text-[9px] font-bold grid place-items-center">
            {triggered.length || '!'}
          </span>
        )}
      </button>
      {open && (
        <div className="rise-in absolute right-0 top-9 z-40 w-80 bg-ink-900 border border-ink-600 rounded-xl shadow-xl shadow-black/50 p-3">
          <h4 className="text-xs uppercase tracking-wider text-mist-400 mb-2">Price alerts</h4>
          {alerts.length === 0 && (
            <p className="text-xs text-mist-400">No alerts yet — set one from the 🔔+ button on any chart.</p>
          )}
          {triggered.length > 0 && (
            <div className="space-y-1 mb-2">
              {triggered.map((a) => (
                <div key={a.id} className="flex items-center gap-2 bg-brass-400/10 border border-brass-400/40 rounded-lg px-2.5 py-1.5">
                  <button onClick={() => { onOpenSymbol(a.symbol); setOpen(false) }} className="flex-1 text-left">
                    <span className="price text-xs text-mist-50">{a.symbol}</span>
                    <span className="block text-[10px] text-brass-300">
                      crossed {a.direction} {a.price} · now {a.triggered_price}
                    </span>
                  </button>
                  <button onClick={() => { api.deleteAlert(a.id).then(load) }} className="text-mist-400 hover:text-bear-500 text-xs px-1">×</button>
                </div>
              ))}
            </div>
          )}
          {active.map((a) => (
            <div key={a.id} className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-ink-800">
              <button onClick={() => { onOpenSymbol(a.symbol); setOpen(false) }} className="flex-1 text-left">
                <span className="price text-xs text-mist-200">{a.symbol}</span>
                <span className="block text-[10px] text-mist-400">waiting: {a.direction} {a.price}</span>
              </button>
              <button onClick={() => { api.deleteAlert(a.id).then(load) }} className="text-mist-400 hover:text-bear-500 text-xs px-1">×</button>
            </div>
          ))}
          <p className="text-[9px] text-mist-400/60 mt-2">Checked every 5 minutes while the app is open.</p>
        </div>
      )}
    </div>
  )
}
