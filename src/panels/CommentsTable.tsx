import { useEffect, useMemo, useState } from 'react'
import { loadCommentsRaw } from '../data/loaders'
import type { CommentsRawPayload, RawComment, Stance } from '../data/types'

/** Stance is never encoded by color alone: each one has a distinct glyph and word. */
const STANCE: Record<Stance, { glyph: string; label: string; cls: string }> = {
  support: { glyph: '▲', label: 'Support', cls: 'bg-emerald-100 text-emerald-900 border-emerald-300' },
  oppose: { glyph: '▼', label: 'Oppose', cls: 'bg-rose-100 text-rose-900 border-rose-300' },
  neutral: { glyph: '●', label: 'Neutral', cls: 'bg-sky-100 text-sky-900 border-sky-300' },
  unclear: { glyph: '?', label: 'Unclear', cls: 'bg-stone-200 text-stone-800 border-stone-400' },
}
const STANCES: Stance[] = ['support', 'oppose', 'neutral', 'unclear']

function StanceBadge({ s }: { s: Stance }) {
  const d = STANCE[s]
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${d.cls}`}>
      <span aria-hidden>{d.glyph}</span>
      {d.label}
    </span>
  )
}

function fmtDate(iso: string) {
  if (!iso) return '—'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? iso : d.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })
}

function shortTitle(t: string) {
  return t.replace(/\s*-\s*TO BE HEARD.*$/i, '').trim()
}

export default function CommentsTable() {
  const [data, setData] = useState<CommentsRawPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [item, setItem] = useState<string>('all')
  const [stances, setStances] = useState<Set<Stance>>(new Set(STANCES))
  const [q, setQ] = useState('')
  const [hideDupes, setHideDupes] = useState(false)

  useEffect(() => {
    loadCommentsRaw().then(setData).catch((e) => setError(String(e)))
  }, [])

  const filtered = useMemo(() => {
    if (!data) return []
    const needle = q.trim().toLowerCase()
    return data.comments.filter(
      (c) =>
        (item === 'all' || c.item === item) &&
        stances.has(c.stance) &&
        (!hideDupes || !c.duplicate_of) &&
        (!needle || c.text.toLowerCase().includes(needle) || c.comment_id.toLowerCase().includes(needle)),
    )
  }, [data, item, stances, q, hideDupes])

  const stanceCounts = useMemo(() => {
    const m: Record<Stance, number> = { support: 0, oppose: 0, neutral: 0, unclear: 0 }
    for (const c of filtered) m[c.stance]++
    return m
  }, [filtered])

  if (error)
    return (
      <div className="m-8 rounded-lg border border-rose-300 bg-rose-50 p-4 text-rose-900">
        <strong>Could not load comments.</strong> {error}
        <div className="mt-1 text-sm">Run <code>npm run data</code> (or <code>npm run data:offline</code>) first.</div>
      </div>
    )
  if (!data) return <div className="m-8 animate-pulse text-stone-500">Loading comments…</div>

  const toggleStance = (s: Stance) =>
    setStances((prev) => {
      const n = new Set(prev)
      if (n.has(s)) n.delete(s)
      else n.add(s)
      return n
    })

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Civic Voice Map</h1>
        <p className="text-sm text-stone-600">
          Milestone 1 proof: <strong>{data.comments.length.toLocaleString()}</strong> real public eComments scraped from
          San José City Council agenda items. Commenter names, emails and addresses were dropped at ingest.
        </p>
      </header>

      {/* Item picker */}
      <nav aria-label="Agenda item" className="mb-3 flex flex-wrap gap-2">
        <ItemChip active={item === 'all'} onClick={() => setItem('all')} title="All items" count={data.comments.length} />
        {data.items.map((m) => (
          <ItemChip
            key={m.item}
            active={item === m.item}
            onClick={() => setItem(m.item)}
            title={`${m.meeting_date} · ${shortTitle(m.item_title)}`}
            count={m.scraped_count}
            declared={m.declared_count}
          />
        ))}
      </nav>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-stone-200 bg-white p-3">
        <span className="text-xs font-semibold uppercase tracking-wide text-stone-500">Stance</span>
        {STANCES.map((s) => (
          <button
            key={s}
            type="button"
            aria-pressed={stances.has(s)}
            onClick={() => toggleStance(s)}
            className={`rounded-full border px-2.5 py-1 text-xs ${stances.has(s) ? STANCE[s].cls : 'border-stone-200 bg-stone-50 text-stone-400 line-through'}`}
          >
            <span aria-hidden>{STANCE[s].glyph}</span> {STANCE[s].label} ({stanceCounts[s]})
          </button>
        ))}
        <label className="ml-2 flex items-center gap-1 text-xs text-stone-700">
          <input type="checkbox" checked={hideDupes} onChange={(e) => setHideDupes(e.target.checked)} />
          collapse exact-text repeats
        </label>
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search text or id…"
          aria-label="Search comments"
          className="ml-auto w-64 rounded-md border border-stone-300 px-2 py-1 text-sm"
        />
      </div>

      <p className="mb-2 text-sm text-stone-600" aria-live="polite">
        Showing <strong>{filtered.length.toLocaleString()}</strong> of {data.comments.length.toLocaleString()} comments
      </p>

      {filtered.length === 0 ? (
        <div className="rounded-lg border border-dashed border-stone-300 p-8 text-center text-stone-500">No comments match these filters.</div>
      ) : (
        <ol className="space-y-2">
          {filtered.map((c) => (
            <CommentRow key={c.comment_id} c={c} showItem={item === 'all'} />
          ))}
        </ol>
      )}

      <footer className="mt-8 border-t border-stone-200 pt-4 text-xs text-stone-500">
        <div>Source: {data.source}. Generated {fmtDate(data.generated_at)}.</div>
        <div>
          Items scraped:{' '}
          {data.items.map((m) => (
            <span key={m.item} className="mr-3">
              <a className="underline" href={m.source_url} target="_blank" rel="noreferrer">
                {m.item}
              </a>{' '}
              ({m.scraped_count}/{m.declared_count} declared, {m.exact_duplicates} exact repeats)
            </span>
          ))}
        </div>
        <div>Stance is the commenter's self-reported position on the Granicus form. Dates come from the comment id's creation timestamp.</div>
      </footer>
    </div>
  )
}

function ItemChip({ active, onClick, title, count, declared }: { active: boolean; onClick: () => void; title: string; count: number; declared?: number }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`max-w-md truncate rounded-md border px-3 py-1.5 text-left text-sm ${active ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-stone-300 bg-white hover:bg-stone-100'}`}
      title={title}
    >
      {title} <span className={active ? 'opacity-80' : 'text-stone-500'}>· {count}{declared !== undefined && declared !== count ? `/${declared}` : ''}</span>
    </button>
  )
}

function CommentRow({ c, showItem }: { c: RawComment; showItem: boolean }) {
  return (
    <li className="rounded-lg border border-stone-200 bg-white p-3">
      <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-stone-500">
        <code className="rounded bg-stone-100 px-1.5 py-0.5 font-mono text-stone-700">{c.comment_id}</code>
        <StanceBadge s={c.stance} />
        <span>{fmtDate(c.received_at)}</span>
        {showItem && <span className="truncate text-stone-600">{c.item} · {shortTitle(c.item_title)}</span>}
        <span className="rounded bg-stone-100 px-1.5 py-0.5">{c.channel}</span>
        {c.duplicate_of && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-900">exact repeat of {c.duplicate_of}</span>}
        <span className="ml-auto italic">name removed at ingest</span>
      </div>
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-stone-900">{c.text}</p>
    </li>
  )
}
