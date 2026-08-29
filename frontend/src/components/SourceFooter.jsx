export default function SourceFooter({ source }) {
  if (!source) return null
  const fetched = source.fetched_at ? new Date(source.fetched_at).toLocaleString() : ''
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-mist-400 border-t border-ink-700 pt-2.5 mt-3">
      <span className="uppercase tracking-wider text-mist-400/70">Source</span>
      <a
        href={source.url}
        target="_blank"
        rel="noreferrer"
        className="text-brass-400 hover:text-brass-300 underline decoration-brass-400/30 underline-offset-2"
      >
        {source.provider}
      </a>
      <span aria-hidden="true">·</span>
      <span>fetched {fetched}</span>
      {source.note && (
        <span className="w-full text-mist-400/80 italic">{source.note}</span>
      )}
    </div>
  )
}
