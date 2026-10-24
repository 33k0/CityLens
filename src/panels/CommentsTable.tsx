import { useEffect, useMemo, useState } from 'react'
import { load311ByTract, loadVoice } from '../data/loaders'
import type { CommenterType, Stance, VoiceComment, VoiceItem, VoicePayload } from '../data/types'
import ProvenanceChips from './ProvenanceChips'
import Requests311 from './Requests311'
import Inbox from './Inbox'

/** Stance is never encoded by color alone: each one has a distinct glyph and word. */
const STANCE: Record<Stance, { glyph: string; label: string; cls: string }> = {
  support: { glyph: '▲', label: 'Support', cls: 'bg-emerald-100 text-emerald-900 border-emerald-300' },
  oppose: { glyph: '▼', label: 'Oppose', cls: 'bg-rose-100 text-rose-900 border-rose-300' },
  neutral: { glyph: '●', label: 'Neutral', cls: 'bg-sky-100 text-sky-900 border-sky-300' },
  unclear: { glyph: '?', label: 'Unclear', cls: 'bg-stone-200 text-stone-800 border-stone-400' },
}
const STANCES: Stance[] = ['support', 'oppose', 'neutral', 'unclear']
const TYPE_LABEL: Record<CommenterType, string> = { resident: 'resident', organization: 'organization', developer_or_counsel: 'developer / counsel', government: 'government' }
const TYPE_CLS: Record<CommenterType, string> = { resident: 'bg-stone-100 text-stone-800', organization: 'bg-violet-100 text-violet-900', developer_or_counsel: 'bg-orange-100 text-orange-900', government: 'bg-sky-100 text-sky-900' }
const PRECISION_LABEL: Record<string, string> = { address: 'located by address', neighborhood: 'located by neighborhood', zip: 'located by zip', district: 'council district only', none: 'no location' }
const SOURCE_LABEL: Record<string, string> = { intersection: 'intersection', street_anchor: 'street, approximate', landmark: 'landmark', signature: 'signature block', body: 'text', subject: 'subject line' }
const BASIS_LABEL: Record<string, string> = { residence: 'where the writer is', issue: 'place the comment is about', both: 'writer’s own area' }
type View = { kind: '311' } | { kind: 'inbox' } | { kind: 'voice'; item: string } // item 'all' = all voice
type ChannelF = 'all' | 'letter' | 'email'

function fmtDate(iso: string) {
  if (!iso) return 'date not in header'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? iso : d.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })
}
const shortTitle = (t: string) => t.replace(/\s*-\s*TO BE HEARD.*$/i, '').trim()

/** Text with the evidence quote highlighted (exact substring by construction). */
function Highlighted({ text, quote }: { text: string; quote: string }) {
  const i = quote ? text.indexOf(quote) : -1
  if (i < 0) return <>{text}</>
  return (
    <>
      {text.slice(0, i)}
      <mark className="rounded bg-yellow-200 px-0.5">{quote}</mark>
      {text.slice(i + quote.length)}
    </>
  )
}

export default function CommentsTable() {
  const [data, setData] = useState<VoicePayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<View>({ kind: 'voice', item: 'all' })
  const [n311, setN311] = useState<number | null>(null)
  const [q, setQ] = useState('')
  const [channelF, setChannelF] = useState<ChannelF>('all')
  const [stances, setStances] = useState<Set<Stance>>(new Set(STANCES))
  const [cat, setCat] = useState('all')
  const [collapse, setCollapse] = useState(true)
  const [sourceF, setSourceF] = useState<'all' | 'real' | 'simulated'>('all')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  useEffect(() => {
    loadVoice().then(setData).catch((e) => setError(String(e)))
    load311ByTract().then((d) => setN311(d.rows_located)).catch(() => setN311(null))
  }, [])

  const catLabel = useMemo(() => Object.fromEntries((data?.categories ?? []).flatMap((c) => [[c.key, c.label] as const, ...(c.subcategories ?? []).map((x) => [x.key, x.label] as const)])), [data])
  const [sub, setSub] = useState('all')
  const items = useMemo(() => (data?.items ?? []).filter((it) => sourceF === 'all' || (sourceF === 'real' ? !it.mock : it.mock)), [data, sourceF])

  const filtered = useMemo(() => {
    if (!data || view.kind !== 'voice') return []
    const needle = q.trim().toLowerCase()
    const allowedItems = new Set(items.map((i) => i.item))
    const seenCampaign = new Set<string>()
    return data.comments.filter((c) => {
      if (view.item === 'all' ? !allowedItems.has(c.item) : c.item !== view.item) return false
      if (channelF !== 'all' && c.channel !== channelF) return false
      if (!stances.has(c.stance)) return false
      if (cat !== 'all' && c.category !== cat) return false
      if (sub !== 'all' && c.subcategory !== sub) return false
      if (collapse) {
        if (c.duplicate_of) return false
        if (c.campaign_id) {
          if (seenCampaign.has(c.campaign_id)) return false
          seenCampaign.add(c.campaign_id)
        }
      }
      return !needle || c.text.toLowerCase().includes(needle) || c.subject.toLowerCase().includes(needle) || c.comment_id.toLowerCase().includes(needle)
    })
  }, [data, view, q, channelF, stances, cat, sub, collapse, items])

  const counts = useMemo(() => {
    const s: Record<string, number> = {}
    const c: Record<string, number> = {}
    const sc: Record<string, number> = {}
    for (const x of filtered) {
      sc[x.subcategory || ''] = (sc[x.subcategory || ''] ?? 0) + 1
      s[x.stance] = (s[x.stance] ?? 0) + 1
      c[x.category || 'unlabeled'] = (c[x.category || 'unlabeled'] ?? 0) + 1
    }
    return { s, c, sc }
  }, [filtered])

  if (error)
    return (
      <div className="m-8 rounded-lg border border-rose-300 bg-rose-50 p-4 text-rose-900">
        <strong>Could not load comments.</strong> {error}
        <div className="mt-1 text-sm">Run <code>npm run data</code> (or <code>npm run data:offline</code>) first.</div>
      </div>
    )
  if (!data) return <div className="m-8 animate-pulse text-stone-500">Loading comments…</div>

  const letters = data.channels.letter?.count ?? 0
  const emails = data.channels.email?.count ?? 0
  const letterItems = data.items.filter((i) => !i.mock).length
  const sel: VoiceItem | null = view.kind === 'voice' && view.item !== 'all' ? data.items.find((i) => i.item === view.item) ?? null : null
  const toggle = (id: string) => setExpanded((p) => { const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n })
  const toggleStance = (s: Stance) => setStances((p) => { const n = new Set(p); if (n.has(s)) n.delete(s); else n.add(s); return n })
  const isActive = (v: View) => JSON.stringify(v) === JSON.stringify(view)

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Civic Voice Map</h1>
        <p className="text-sm text-stone-600">
          Written public comment to the San José City Council, and the city's 311 problem reports, kept as separate families. Names, emails and phone numbers are removed at ingest; nothing finer than a census tract is kept.
        </p>
        <div className="mt-2"><ProvenanceChips letterItems={letterItems} letters={letters} requests311={n311} emails={emails} site={data.channels.site?.count ?? 0} /></div>
      </header>

      <div className="grid gap-4 md:grid-cols-[320px_1fr]">
        <aside className="md:sticky md:top-4 md:self-start">
          <div className="mb-2 flex items-center gap-2 text-xs">
            <span className="font-semibold uppercase tracking-wide text-stone-500">Items</span>
            <select value={sourceF} onChange={(e) => setSourceF(e.target.value as typeof sourceF)} aria-label="Item source" className="rounded border border-stone-300 bg-white px-1 py-0.5">
              <option value="all">real + simulated</option>
              <option value="real">real (Legistar) only</option>
              <option value="simulated">simulated only</option>
            </select>
          </div>
          <nav aria-label="Items" className="max-h-[75vh] space-y-1 overflow-y-auto pr-1">
            <NavButton active={isActive({ kind: '311' })} onClick={() => setView({ kind: '311' })} label="Citywide 311 — problems layer" sub={n311 === null ? 'layer not built yet' : 'real · separate family, own scale'} count={n311 ?? 0} tone="problems" />
            <NavButton active={isActive({ kind: 'voice', item: 'all' })} onClick={() => setView({ kind: 'voice', item: 'all' })} label="All items — voice" sub={`${items.length} items · letters + email · never summed with 311`} count={items.reduce((s, i) => s + i.count, 0)} />
            <NavButton active={isActive({ kind: 'inbox' })} onClick={() => setView({ kind: 'inbox' })} label="Inbox — emails as received" sub="simulated" count={emails} />
            {items.map((m) => (
              <NavButton key={m.item} active={isActive({ kind: 'voice', item: m.item })} onClick={() => setView({ kind: 'voice', item: m.item })}
                label={`${m.item} · ${shortTitle(m.title)}`} sub={`${m.meeting_date || 'no meeting date'} · ${m.mock ? 'simulated' : 'real'}${m.count_unique !== m.count ? ` · ${m.count_unique} unique` : ''}`} count={m.count} />
            ))}
          </nav>
        </aside>

        <main>
          {view.kind === '311' ? <Requests311 voice={data.comments} /> : view.kind === 'inbox' ? <Inbox /> : (
            <>
              {sel && (
                <div className="mb-3 rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2 font-medium">
                    <span className={`rounded-full px-2 py-0.5 text-[11px] text-white ${sel.mock ? 'bg-amber-600' : 'bg-indigo-600'}`}>voice · {sel.channels.join(' + ')} · {sel.mock ? 'simulated' : 'real'}</span>
                    {sel.item} · {sel.title}
                  </div>
                  {sel.pages_summary && <div className="mt-1 font-medium text-indigo-950">Pages of record: {sel.pages_summary}</div>}
                  <div className="text-stone-600">
                    {sel.meeting_date ? `Council ${sel.meeting_date} · ` : ''}{sel.count} comments, {sel.count_unique} after collapsing duplicates and campaigns
                    {sel.source_url && <> · <a className="underline" href={sel.source_url} target="_blank" rel="noreferrer">Legistar</a></>}
                  </div>
                </div>
              )}

              <div className="mb-3 space-y-2 rounded-lg border border-stone-200 bg-white p-3 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="w-16 font-semibold uppercase tracking-wide text-stone-500">Channel</span>
                  {(['all', 'letter', 'email'] as ChannelF[]).map((c) => (
                    <button key={c} type="button" aria-pressed={channelF === c} onClick={() => setChannelF(c)} className={`rounded-full border px-2.5 py-1 ${channelF === c ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-stone-300 bg-white'}`}>
                      {c === 'all' ? 'all voice' : c === 'letter' ? 'letters (real)' : 'email (simulated)'}
                    </button>
                  ))}
                  <label className="ml-2 flex items-center gap-1 text-stone-700"><input type="checkbox" checked={collapse} onChange={(e) => setCollapse(e.target.checked)} /> count duplicates and form-letter campaigns once</label>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="w-16 font-semibold uppercase tracking-wide text-stone-500">Stance</span>
                  {STANCES.map((s) => (
                    <button key={s} type="button" aria-pressed={stances.has(s)} onClick={() => toggleStance(s)} className={`rounded-full border px-2.5 py-1 ${stances.has(s) ? STANCE[s].cls : 'border-stone-200 bg-stone-50 text-stone-400 line-through'}`}>
                      <span aria-hidden>{STANCE[s].glyph}</span> {STANCE[s].label} ({counts.s[s] ?? 0})
                    </button>
                  ))}
                </div>
                {data.categories.length > 0 && (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="w-16 font-semibold uppercase tracking-wide text-stone-500">Category</span>
                    <button type="button" aria-pressed={cat === 'all'} onClick={() => { setCat('all'); setSub('all') }} className={`rounded-full border px-2.5 py-1 ${cat === 'all' ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-stone-300 bg-white'}`}>all</button>
                    {data.categories.map((c) => (
                      <button key={c.key} type="button" title={c.description} aria-pressed={cat === c.key} onClick={() => { setCat(c.key); setSub('all') }} className={`rounded-full border px-2.5 py-1 ${cat === c.key ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-stone-300 bg-white'}`}>
                        {c.label} ({counts.c[c.key] ?? 0})
                      </button>
                    ))}
                  </div>
                )}
                {cat !== 'all' && (data.categories.find((c) => c.key === cat)?.subcategories?.length ?? 0) > 0 && (
                  <div className="flex flex-wrap items-center gap-2 pl-[4.5rem]">
                    <button type="button" aria-pressed={sub === 'all'} onClick={() => setSub('all')} className={`rounded-full border px-2 py-0.5 ${sub === 'all' ? 'border-indigo-400 bg-indigo-100' : 'border-stone-300 bg-white'}`}>all subcategories</button>
                    {data.categories.find((c) => c.key === cat)!.subcategories.map((x) => (
                      <button key={x.key} type="button" title={x.description} aria-pressed={sub === x.key} onClick={() => setSub(x.key)} className={`rounded-full border px-2 py-0.5 ${sub === x.key ? 'border-indigo-400 bg-indigo-100' : 'border-stone-300 bg-white'}`}>
                        {x.label} ({counts.sc[x.key] ?? 0})
                      </button>
                    ))}
                  </div>
                )}
                <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search text, subject, id…" aria-label="Search comments" className="w-full rounded-md border border-stone-300 px-2 py-1 text-sm" />
              </div>

              <p className="mb-2 text-sm text-stone-600" aria-live="polite">Showing <strong>{filtered.length.toLocaleString()}</strong> voice comments{collapse ? ' (duplicates and campaign repeats collapsed)' : ''}</p>

              {filtered.length === 0 ? (
                <div className="rounded-lg border border-dashed border-stone-300 p-8 text-center text-stone-500">No comments match these filters.</div>
              ) : (
                <ol className="space-y-2">
                  {filtered.map((c) => (
                    <Row key={c.comment_id} c={c} showItem={view.item === 'all'} catLabel={catLabel} open={expanded.has(c.comment_id)} onToggle={() => toggle(c.comment_id)} campaignSize={collapse && c.campaign_id ? data.comments.filter((x) => x.campaign_id === c.campaign_id).length : 0} />
                  ))}
                </ol>
              )}
              <footer className="mt-8 border-t border-stone-200 pt-4 text-xs text-stone-500">
                {data.note} Letters are real (Legistar, OCR'd where scanned); emails are simulated and labeled. Highlighted text is the exact evidence quote behind each category. Generated {fmtDate(data.generated_at)}.
              </footer>
            </>
          )}
        </main>
      </div>
    </div>
  )
}

function NavButton({ active, onClick, label, sub, count, tone }: { active: boolean; onClick: () => void; label: string; sub: string; count: number; tone?: 'problems' }) {
  const on = tone === 'problems' ? 'border-emerald-700 bg-emerald-700 text-white' : 'border-indigo-600 bg-indigo-600 text-white'
  return (
    <button type="button" aria-pressed={active} onClick={onClick} className={`flex w-full items-start gap-2 rounded-md border px-2.5 py-1.5 text-left text-xs ${active ? on : 'border-stone-200 bg-white hover:bg-stone-100'}`} title={label}>
      <span className="min-w-0 flex-1">
        <span className="line-clamp-2">{label}</span>
        <span className={`block ${active ? 'opacity-80' : 'text-stone-500'}`}>{sub}</span>
      </span>
      <span className={`shrink-0 rounded-full px-1.5 py-0.5 font-mono ${active ? 'bg-white/20' : 'bg-stone-100 text-stone-700'}`}>{count.toLocaleString()}</span>
    </button>
  )
}

function Row({ c, showItem, catLabel, open, onToggle, campaignSize }: { c: VoiceComment; showItem: boolean; catLabel: Record<string, string>; open: boolean; onToggle: () => void; campaignSize: number }) {
  const long = c.text.length > 700
  const s = STANCE[c.stance] ?? STANCE.unclear
  return (
    <li className="rounded-lg border border-stone-200 bg-white p-3">
      <div className="mb-1 flex flex-wrap items-center gap-1.5 text-xs text-stone-500">
        <code className="rounded bg-stone-100 px-1.5 py-0.5 font-mono text-stone-700">{c.comment_id}</code>
        <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-medium ${s.cls}`} title={c.stance_evidence ? `stance evidence: “${c.stance_evidence}” (${c.stance_source})` : c.stance_source}><span aria-hidden>{s.glyph}</span>{s.label}</span>
        {c.category && <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-indigo-900" title={c.inherited_from ? `label inherited from ${c.inherited_from} (same campaign text)` : undefined}>{catLabel[c.category] ?? c.category}{c.subcategory ? ` › ${catLabel[c.subcategory] ?? c.subcategory}` : ''}{c.confidence !== null ? ` · ${Math.round(c.confidence * 100)}%` : ''}</span>}
        <span className={`rounded px-1.5 py-0.5 ${c.mock ? 'bg-amber-100 text-amber-900' : 'bg-emerald-100 text-emerald-900'}`}>{c.channel} · {c.mock ? 'simulated' : 'real'}</span>
        <span className={`rounded px-1.5 py-0.5 ${TYPE_CLS[c.commenter_type] ?? 'bg-stone-100'}`}>{TYPE_LABEL[c.commenter_type] ?? c.commenter_type}</span>
        <span>{fmtDate(c.received_at)}</span>
        {showItem && <span className="max-w-xs truncate text-stone-600">{c.item} · {shortTitle(c.item_title)}</span>}
        <span className="rounded bg-teal-50 px-1.5 py-0.5 text-teal-900" title={c.location_basis ? `Location basis: ${BASIS_LABEL[c.location_basis] ?? c.location_basis}` : undefined}>
          {PRECISION_LABEL[c.location_precision] ?? c.location_precision}
          {c.location_source && SOURCE_LABEL[c.location_source] ? ` (${SOURCE_LABEL[c.location_source]})` : ''}
          {c.tract_id ? ` · tract ${c.tract_id}` : ''}{c.multi_tract ? ' · spans tracts' : ''}
          {c.location_basis ? ` · ${BASIS_LABEL[c.location_basis] ?? c.location_basis}` : ''}
        </span>
        {c.campaign_id && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-900">campaign {c.campaign_id}{campaignSize ? ` · ${campaignSize} copies` : ''}</span>}
        {c.duplicate_of && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-900">duplicate of {c.duplicate_of}</span>}
        {c.ocr && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-900">OCR</span>}
        {c.language !== 'en' && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-900">lang: {c.language}</span>}
        {c.pages_exhibit ? <span className="rounded bg-stone-100 px-1.5 py-0.5">{c.pages_total} pp incl. {c.pages_exhibit} exhibit</span> : null}
        <span className="ml-auto italic">name removed at ingest</span>
      </div>
      {c.subject && <div className="mb-1 text-sm font-medium text-stone-800">{c.subject}</div>}
      <p className={`whitespace-pre-wrap text-sm leading-relaxed text-stone-900 ${long && !open ? 'line-clamp-6' : ''}`}><Highlighted text={c.text} quote={c.evidence_quote} /></p>
      {long && <button type="button" onClick={onToggle} className="mt-1 text-xs text-indigo-700 underline">{open ? 'Show less' : `Show full text (${c.text.length.toLocaleString()} chars)`}</button>}
    </li>
  )
}
