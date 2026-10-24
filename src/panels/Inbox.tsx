import { useEffect, useState } from 'react'
import { loadInbox } from '../data/loaders'
import type { InboxEmail } from '../data/types'

/** Simulated emails as received (sender removed at ingest). Voice family, simulated channel. */
export default function Inbox() {
  const [emails, setEmails] = useState<InboxEmail[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  useEffect(() => {
    loadInbox().then((d) => setEmails(d.emails)).catch((e) => setError(String(e)))
  }, [])
  if (error) return <div className="rounded-lg border border-stone-300 bg-stone-50 p-4 text-sm">Inbox not built yet ({error}). Run <code>npm run data</code>.</div>
  if (!emails) return <div className="animate-pulse text-stone-500">Loading inbox…</div>
  const sel = emails.find((e) => e.comment_id === open) ?? null
  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
        <span className="mr-2 rounded-full bg-amber-600 px-2 py-0.5 text-[11px] text-white">voice · email · simulated</span>
        {emails.length} emails as received by council offices. Sender names and addresses were removed at ingest. Attachments are listed but not shown until redacted.
      </div>
      <div className="grid gap-3 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <ol className="max-h-[70vh] divide-y divide-stone-100 overflow-y-auto rounded-lg border border-stone-200 bg-white" aria-label="Inbox">
          {emails.map((e) => (
            <li key={e.comment_id}>
              <button type="button" onClick={() => setOpen(e.comment_id)} aria-pressed={open === e.comment_id}
                className={`block w-full px-3 py-2 text-left text-xs ${open === e.comment_id ? 'bg-indigo-50' : 'hover:bg-stone-50'}`}>
                <div className="flex items-center gap-2 text-stone-500">
                  <span>{new Date(e.received_at).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })}</span>
                  <span className="truncate">to {e.to}</span>
                  {e.attachments.length > 0 && <span aria-label="has attachment">📎</span>}
                  {e.submitted_via === 'ecomments_portal' && <span className="rounded bg-stone-100 px-1">portal</span>}
                  {e.language !== 'en' && <span className="rounded bg-amber-100 px-1 text-amber-900">{e.language}</span>}
                </div>
                <div className="truncate text-sm font-medium text-stone-900">{e.subject || '(no subject)'}</div>
                <div className="truncate text-stone-600">{e.body.slice(0, 120)}</div>
              </button>
            </li>
          ))}
        </ol>
        <article className="rounded-lg border border-stone-200 bg-white p-4 text-sm">
          {sel ? (
            <>
              <h3 className="text-base font-semibold">{sel.subject || '(no subject)'}</h3>
              <dl className="mb-3 mt-1 grid grid-cols-[4rem_1fr] gap-x-2 text-xs text-stone-600">
                <dt>From</dt><dd className="italic">{sel.from}</dd>
                <dt>To</dt><dd>{sel.to}</dd>
                <dt>Date</dt><dd>{new Date(sel.received_at).toLocaleString()}</dd>
                <dt>Item</dt><dd>{sel.item} · {sel.item_title}</dd>
                <dt>Id</dt><dd className="font-mono">{sel.comment_id}</dd>
              </dl>
              <p className="whitespace-pre-wrap leading-relaxed">{sel.body}</p>
              {sel.attachments.length > 0 && (
                <ul className="mt-3 space-y-1 text-xs">
                  {sel.attachments.map((a) => (
                    <li key={a.file} className="rounded border border-stone-200 bg-stone-50 px-2 py-1">📎 {a.file}{a.description ? ` — ${a.description}` : ''} <span className="text-stone-500">({a.kind}; {a.redacted ? 'redacted' : 'not yet redacted, not displayed'})</span></li>
                  ))}
                </ul>
              )}
            </>
          ) : <p className="text-stone-500">Select an email.</p>}
        </article>
      </div>
    </div>
  )
}
