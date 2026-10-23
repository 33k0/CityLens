import { useEffect, useMemo, useState } from 'react'
import { loadCommentsRaw } from '../data/loaders'
import type { CommenterType, CommentsRawPayload, ItemMeta, RawComment, Stance } from '../data/types'
import ProvenanceChips from './ProvenanceChips'
import Requests311 from './Requests311'
import { load311ByTract } from '../data/loaders'

/** Stance is never encoded by color alone: each one has a distinct glyph and word. */
const STANCE: Record<Stance, { glyph: string; label: string; cls: string }> = {
  support: { glyph: '▲', label: 'Support', cls: 'bg-emerald-100 text-emerald-900 border-emerald-300' },
  oppose: { glyph: '▼', label: 'Oppose', cls: 'bg-rose-100 text-rose-900 border-rose-300' },
  neutral: { glyph: '●', label: 'Neutral', cls: 'bg-sky-100 text-sky-900 border-sky-300' },
  unclear: { glyph: '?', label: 'Unclear', cls: 'bg-stone-200 text-stone-800 border-stone-400' },
}
type ItemSort = 'letters' | 'date'
type TypeFilter = 'all' | CommenterType
const TYPES: CommenterType[] = ['resident', 'organization', 'developer_or_counsel', 'government']
const TYPE_LABEL: Record<CommenterType, string> = { resident: 'resident', organization: 'organization', developer_or_counsel: 'developer / counsel', government: 'government' }
const TYPE_CLS: Record<CommenterType, string> = { resident: 'bg-stone-100 text-stone-800', organization: 'bg-violet-100 text-violet-900', developer_or_counsel: 'bg-orange-100 text-orange-900', government: 'bg-sky-100 text-sky-900' }

function fmtDate(iso: string) {
  if (!iso) return 'date not in header'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? iso : d.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })
}
const shortTitle = (t: string) => t.replace(/\s*-\s*TO BE HEARD.*$/i, '').trim()

export default function CommentsTable() {
  const [data, setData] = useState<CommentsRawPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [item, setItem] = useState<string>('all')
  const [q, setQ] = useState('')
  const [typeF, setTypeF] = useState<TypeFilter>('all')
  const [hideDupes, setHideDupes] = useState(false)
  const [priorityOnly, setPriorityOnly] = useState(false)
  const [sort, setSort] = useState<ItemSort>('letters')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [n311, setN311] = useState<number | null>(null)

  useEffect(() => {
    loadCommentsRaw().then(setData).catch((e) => setError(String(e)))
    load311ByTract().then((d) => setN311(d.rows_located)).catch(() => setN311(null))
  }, [])

  /** One entry per matter (a matter can have several "Letters" PDFs). */
  const matters = useMemo(() => {
    if (!data) return []
    const m = new Map<string, ItemMeta & { pdf_count: number }>()
    for (const it of data.items) {
      const prev = m.get(it.item)
      if (prev) {
        prev.letters += it.letters
        prev.pages += it.pages
        prev.ocr_pages += it.ocr_pages
        prev.organizations += it.organizations
        prev.pdf_count += it.pdfs?.length ?? 1
      } else m.set(it.item, { ...it, pdf_count: it.pdfs?.length ?? 1 })
    }
    let arr = [...m.values()]
    if (priorityOnly) arr = arr.filter((x) => x.priority)
    arr.sort((a, b) => (sort === 'letters' ? b.letters - a.letters || b.meeting_date.localeCompare(a.meeting_date) : b.meeting_date.localeCompare(a.meeting_date)))
    return arr
  }, [data, sort, priorityOnly])

  const filtered = useMemo(() => {
    if (!data) return []
    const needle = q.trim().toLowerCase()
    const allowed = priorityOnly ? new Set(matters.map((m) => m.item)) : null
    return data.comments.filter(
      (c) =>
        (item === 'all' ? !allowed || allowed.has(c.item) : c.item === item) &&
        (typeF === 'all' || c.commenter_type === typeF) &&
        (!hideDupes || !c.duplicate_of) &&
        (!needle || c.text.toLowerCase().includes(needle) || c.subject.toLowerCase().includes(needle) || c.comment_id.toLowerCase().includes(needle) || c.item.includes(needle)),
    )
  }, [data, item, q, typeF, hideDupes, priorityOnly, matters])

  if (error)
    return (
      <div className="m-8 rounded-lg border border-rose-300 bg-rose-50 p-4 text-rose-900">
        <strong>Could not load comments.</strong> {error}
        <div className="mt-1 text-sm">Run <code>npm run data</code> (or <code>npm run data:offline</code>) first.</div>
      </div>
    )
  if (!data) return <div className="m-8 animate-pulse text-stone-500">Loading comments…</div>

  const total = data.comments.length
  const sel = item === 'all' || item === '311' ? null : matters.find((m) => m.item === item) ?? null
  const toggle = (id: string) =>
    setExpanded((p) => {
      const n = new Set(p)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Civic Voice Map</h1>
        <p className="text-sm text-stone-600">
          Written public comment to the San José City Council, plus the city's 311 problem reports. Names, emails and phone numbers are removed at ingest; nothing finer than a census tract is kept.
        </p>
        <div className="mt-2"><ProvenanceChips letterItems={new Set(data.comments.map((c) => c.item)).size} letters={total} requests311={n311} emails={0} site={0} /></div>
      </header>

      <div className="grid gap-4 md:grid-cols-[320px_1fr]">
        {/* Item picker */}
        <aside className="md:sticky md:top-4 md:self-start">
          <div className="mb-2 flex items-center gap-2 text-xs">
            <span className="font-semibold uppercase tracking-wide text-stone-500">Matters</span>
            <select value={sort} onChange={(e) => setSort(e.target.value as ItemSort)} aria-label="Sort matters" className="rounded border border-stone-300 bg-white px-1 py-0.5">
              <option value="letters">most letters</option>
              <option value="date">newest meeting</option>
            </select>
            <label className="flex items-center gap-1">
              <input type="checkbox" checked={priorityOnly} onChange={(e) => setPriorityOnly(e.target.checked)} /> land use / housing / transport
            </label>
          </div>
          <nav aria-label="Agenda matter" className="max-h-[75vh] space-y-1 overflow-y-auto pr-1">
            <MatterButton active={item === '311'} onClick={() => setItem('311')} label="Citywide 311 — problems layer" sub={n311 === null ? 'layer not built yet' : 'real · separate family, own scale'} count={n311 ?? 0} />
            <MatterButton active={item === 'all'} onClick={() => setItem('all')} label="All items — voice (letters)" sub={`${matters.length} matters · real · never summed with 311`} count={matters.reduce((s, m) => s + m.letters, 0)} />
            {matters.map((m) => (
              <MatterButton
                key={m.item}
                active={item === m.item}
                onClick={() => setItem(m.item)}
                label={`${m.item} · ${shortTitle(m.item_title)}`}
                sub={`${m.meeting_date}${m.agenda_number ? ` · item ${m.agenda_number}` : ''}${m.priority ? ' · ★' : ''}`}
                count={m.letters}
              />
            ))}
          </nav>
        </aside>

        <main>
          {item === '311' ? (
            <Requests311 voice={data.comments} />
          ) : (
          <>
          {sel && (
            <div className="mb-3 rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2 font-medium">
                <span className="rounded-full bg-indigo-600 px-2 py-0.5 text-[11px] text-white">voice · letters · real</span>
                {sel.item} · {sel.item_title}
              </div>
              <div className="mt-1 font-medium text-indigo-950">Pages of record: {sel.pages_summary}</div>
              <div className="text-stone-600">
                Council {sel.meeting_date}{sel.agenda_number ? ` · agenda item ${sel.agenda_number}` : ''} · {sel.pdf_count} PDF{sel.pdf_count > 1 ? 's' : ''}, {sel.pages} pages ({sel.ocr_pages} OCR, {sel.exhibit_pages} exhibit) · {sel.letters} letters{sel.after_deadline !== null ? ` · ${sel.after_deadline} after deadline` : ' · deadline not recorded'} ·{' '}
                <a className="underline" href={sel.source_url} target="_blank" rel="noreferrer">Legistar</a> ·{' '}
                <a className="underline" href={sel.attachment_url} target="_blank" rel="noreferrer">source PDF</a>
              </div>
            </div>
          )}

          <div className="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-stone-200 bg-white p-3 text-xs">
            <span className="font-semibold uppercase tracking-wide text-stone-500">Sender</span>
            {(['all', ...TYPES] as TypeFilter[]).map((t) => (
              <button key={t} type="button" aria-pressed={typeF === t} onClick={() => setTypeF(t)} className={`rounded-full border px-2.5 py-1 ${typeF === t ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-stone-300 bg-white'}`}>
                {t === 'all' ? 'all' : TYPE_LABEL[t]}
              </button>
            ))}
            <label className="ml-2 flex items-center gap-1 text-stone-700">
              <input type="checkbox" checked={hideDupes} onChange={(e) => setHideDupes(e.target.checked)} /> collapse exact-text repeats
            </label>
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search text, subject, id, matter…" aria-label="Search comments" className="ml-auto w-72 rounded-md border border-stone-300 px-2 py-1 text-sm" />
          </div>

          <p className="mb-2 text-sm text-stone-600" aria-live="polite">
            Showing <strong>{filtered.length.toLocaleString()}</strong> of {total.toLocaleString()} letters
          </p>

          {filtered.length === 0 ? (
            <div className="rounded-lg border border-dashed border-stone-300 p-8 text-center text-stone-500">No letters match these filters.</div>
          ) : (
            <ol className="space-y-2">
              {filtered.map((c) => (
                <LetterRow key={c.comment_id} c={c} showItem={item === 'all'} open={expanded.has(c.comment_id)} onToggle={() => toggle(c.comment_id)} />
              ))}
            </ol>
          )}

          <footer className="mt-8 border-t border-stone-200 pt-4 text-xs text-stone-500">
            <div>Source: {data.source}. Generated {fmtDate(data.generated_at)}.</div>
            <div>
              Voice (letters, later email and site) and Problems (311) are separate families: no count, share or rank on this page adds one to the other. Stance is assigned by the classifier in a later pipeline step (letters carry no self-reported position); until then every letter shows "{STANCE.unclear.glyph} Unclear".
              Dates come from the email's Sent: header. Signature-block addresses are held only in the gitignored raw folder for tract geocoding.
            </div>
          </footer>
          </>
          )}
        </main>
      </div>
    </div>
  )
}

function MatterButton({ active, onClick, label, sub, count }: { active: boolean; onClick: () => void; label: string; sub: string; count: number }) {
  return (
    <button type="button" aria-pressed={active} onClick={onClick} className={`flex w-full items-start gap-2 rounded-md border px-2.5 py-1.5 text-left text-xs ${active ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-stone-200 bg-white hover:bg-stone-100'}`} title={label}>
      <span className="min-w-0 flex-1">
        <span className="line-clamp-2">{label}</span>
        <span className={`block ${active ? 'opacity-80' : 'text-stone-500'}`}>{sub}</span>
      </span>
      <span className={`shrink-0 rounded-full px-1.5 py-0.5 font-mono ${active ? 'bg-white/20' : 'bg-stone-100 text-stone-700'}`}>{count}</span>
    </button>
  )
}

function LetterRow({ c, showItem, open, onToggle }: { c: RawComment; showItem: boolean; open: boolean; onToggle: () => void }) {
  const long = c.text.length > 700
  const s = STANCE[c.stance] ?? STANCE.unclear
  return (
    <li className="rounded-lg border border-stone-200 bg-white p-3">
      <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-stone-500">
        <code className="rounded bg-stone-100 px-1.5 py-0.5 font-mono text-stone-700">{c.comment_id}</code>
        <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-medium ${s.cls}`}><span aria-hidden>{s.glyph}</span>{s.label}</span>
        <span className={`rounded px-1.5 py-0.5 ${TYPE_CLS[c.commenter_type] ?? 'bg-stone-100'}`}>{TYPE_LABEL[c.commenter_type] ?? c.commenter_type}</span>
        {c.pages_exhibit > 0 && <span className="rounded bg-stone-100 px-1.5 py-0.5">{c.pages_total} pp incl. {c.pages_exhibit} exhibit</span>}
        {c.after_deadline && <span className="rounded bg-rose-100 px-1.5 py-0.5 text-rose-900">after deadline</span>}
        <span>{fmtDate(c.received_at)}</span>
        {showItem && <span className="truncate text-stone-600">{c.item} · {shortTitle(c.item_title)}</span>}
        <span className="rounded bg-stone-100 px-1.5 py-0.5">{c.channel} · pp. {c.pdf_page_start}{c.pdf_page_end !== c.pdf_page_start ? `–${c.pdf_page_end}` : ''}</span>
        {c.language !== 'en' && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-900">lang: {c.language}</span>}
        {c.ocr && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-900">OCR</span>}
        {c.has_address_hint && <span className="rounded bg-teal-100 px-1.5 py-0.5 text-teal-900">address in signature (held raw-only)</span>}
        {c.neighborhood && <span className="rounded bg-teal-100 px-1.5 py-0.5 text-teal-900">{c.neighborhood}</span>}
        {c.duplicate_of && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-900">exact repeat of {c.duplicate_of}</span>}
        <span className="ml-auto italic">name, email, phone removed at ingest</span>
      </div>
      {c.subject && <div className="mb-1 text-sm font-medium text-stone-800">{c.subject}</div>}
      <p className={`whitespace-pre-wrap text-sm leading-relaxed text-stone-900 ${long && !open ? 'line-clamp-6' : ''}`}>{c.text}</p>
      {long && (
        <button type="button" onClick={onToggle} className="mt-1 text-xs text-indigo-700 underline">
          {open ? 'Show less' : `Show full letter (${c.text.length.toLocaleString()} chars)`}
        </button>
      )}
    </li>
  )
}
