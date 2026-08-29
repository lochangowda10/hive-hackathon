import { useState } from 'react'

export default function IndicatorChips({ active, onUpdateParams, onRemove }) {
  const [editing, setEditing] = useState(null) // uid
  const [draft, setDraft] = useState({})

  if (active.length === 0) return null

  const startEdit = (inst) => {
    setEditing(inst.uid)
    setDraft({ ...inst.params })
  }

  const apply = (inst) => {
    onUpdateParams(inst.uid, draft)
    setEditing(null)
  }

  return (
    <div className="flex flex-wrap gap-1.5 mt-3">
      {active.map((inst) => (
        <div key={inst.uid} className="relative">
          <span className="inline-flex items-center gap-1.5 text-[11px] price text-mist-200 bg-ink-800 border border-ink-600 rounded-full pl-2.5 pr-1 py-1">
            {inst.label}
            {Object.keys(inst.params || {}).length > 0 && (
              <button onClick={() => (editing === inst.uid ? setEditing(null) : startEdit(inst))}
                      title="Settings"
                      className="text-mist-400 hover:text-brass-400 px-0.5">⚙</button>
            )}
            <button onClick={() => onRemove(inst.uid)} title="Remove"
                    className="text-mist-400 hover:text-bear-500 px-1">×</button>
          </span>

          {editing === inst.uid && (
            <div className="rise-in absolute z-40 top-8 left-0 bg-ink-900 border border-ink-600 rounded-lg p-3 shadow-xl shadow-black/50 min-w-52">
              {Object.entries(inst.paramSpec || {}).map(([name, spec]) => (
                <label key={name} className="block mb-2">
                  <span className="text-[10px] uppercase tracking-wider text-mist-400">{name}</span>
                  {spec.options ? (
                    <select
                      value={draft[name]}
                      onChange={(e) => setDraft({ ...draft, [name]: e.target.value })}
                      className="mt-0.5 w-full bg-ink-800 border border-ink-600 rounded px-2 py-1 text-xs text-mist-50"
                    >
                      {spec.options.map((o) => <option key={o} value={o}>{o}</option>)}
                    </select>
                  ) : (
                    <input
                      type="number" step="any"
                      min={spec.min} max={spec.max}
                      value={draft[name]}
                      onChange={(e) => setDraft({ ...draft, [name]: e.target.value })}
                      className="mt-0.5 w-full bg-ink-800 border border-ink-600 rounded px-2 py-1 text-xs text-mist-50 price"
                    />
                  )}
                </label>
              ))}
              <div className="flex gap-2 mt-1">
                <button onClick={() => apply(inst)}
                        className="text-xs bg-brass-400 hover:bg-brass-300 text-ink-950 font-semibold rounded px-3 py-1">Apply</button>
                <button onClick={() => setEditing(null)}
                        className="text-xs text-mist-400 hover:text-mist-50 px-2">Cancel</button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
