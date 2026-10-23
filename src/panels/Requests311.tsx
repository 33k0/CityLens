import { useEffect, useMemo, useState } from 'react'
import { load311ByTract, load311Sample } from '../data/loaders'
import type { Requests311ByTract, Request311Sample } from '../data/types311'

const LABEL: Record<string, string> = {
  sanitation_dumping: 'Sanitation & dumping', graffiti_blight: 'Graffiti & blight', abandoned_vehicles_parking: 'Abandoned vehicles & parking',
  streets_infrastructure: 'Streets & infrastructure', homelessness_encampments: 'Homelessness & encampments', noise_nuisance: 'Noise & nuisance',
  utilities_billing: 'Utilities & billing', housing: 'Housing', parks_trees: 'Parks & trees', public_safety: 'Public safety', permits_code: 'Permits & code', other: 'Other',
}

/** "Citywide 311 — last 12 months": the real problems layer, as tables until the map lands in Milestone 7. */
export default function Requests311() {
  const [data, setData] = useState<Requests311ByTract | null>(null)
  const [sample, setSample] = useState<Request311Sample | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cat, setCat] = useState('all')
  const [range, setRange] = useState<[number, number] | null>(null) // month index window (client-side slider)

  useEffect(() => {
    load311ByTract().then(setData).catch((e) => setError(String(e)))
    load311Sample().then(setSample).catch(() => setSample(null))
  }, [])

  const stats = useMemo(() => {
    if (!data) return null
    const [lo, hi] = range ?? [0, data.months.length - 1]
    const inWindow = new Set(data.months.slice(lo, hi + 1))
    const byCat: Record<string, number> = {}
    const byMonth: Record<string, number> = {}
    const byTract: Record<string, number> = {}
    for (const [t, cats] of Object.entries(data.by_tract)) {
      for (const [c, months] of Object.entries(cats)) {
        if (cat !== 'all' && c !== cat) continue
        for (const [m, n] of Object.entries(months)) {
          if (!inWindow.has(m)) continue
          byCat[c] = (byCat[c] ?? 0) + n
          byMonth[m] = (byMonth[m] ?? 0) + n
          byTract[t] = (byTract[t] ?? 0) + n
        }
      }
    }
    const tracts = Object.entries(byTract).sort((a, b) => b[1] - a[1])
    const monthMax = Math.max(1, ...Object.values(byMonth))
    const monthsN = Math.max(1, hi - lo + 1)
    const rates = tracts.map(([t, n]) => [t, n, data.population[t] ? (n / data.population[t]) * 1000 * (12 / monthsN) : null] as const)
    const byRate = rates.filter((r) => r[2] !== null).sort((a, b) => (b[2] ?? 0) - (a[2] ?? 0))
    const total = Object.values(byMonth).reduce((a, b) => a + b, 0)
    return { byCat: Object.entries(byCat).sort((a, b) => b[1] - a[1]), byMonth: data.months.map((m) => [m, byMonth[m] ?? 0] as const), monthMax, tracts, tractMax: tracts[0]?.[1] ?? 1, byRate, total, lo, hi, monthsN }
  }, [data, cat, range])

  if (error)
    return (
      <div className="rounded-lg border border-stone-300 bg-stone-50 p-4 text-sm text-stone-700">
        311 layer not built yet ({error}). Run <code>npm run data</code>; it needs <code>public/data/tracts.geojson</code> from <code>build_tracts.py</code>.
      </div>
    )
  if (!data || !stats) return <div className="animate-pulse text-stone-500">Loading 311…</div>

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm">
        <div className="font-medium">Citywide 311 — service requests since {data.since} <span className="ml-1 rounded-full bg-emerald-600 px-2 py-0.5 text-[11px] text-white">problems · 311 · real</span></div>
        <div className="text-stone-700">
          {data.rows_located.toLocaleString()} of {data.rows_total.toLocaleString()} requests located to a San José census tract ({Object.keys(data.by_tract).length} tracts). {data.source}. Coordinates were used for the tract join and discarded; no address exists in this export. Shares and ranks below are within 311 only; they are never pooled with letters or other voice channels, and cross-family comparison uses citywide percentiles of per-1k rates, not raw counts.
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-semibold uppercase tracking-wide text-stone-500">Category</span>
        <button type="button" aria-pressed={cat === 'all'} onClick={() => setCat('all')} className={`rounded-full border px-2.5 py-1 ${cat === 'all' ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-stone-300 bg-white'}`}>all</button>
        {data.categories.map((c) => (
          <button key={c} type="button" aria-pressed={cat === c} onClick={() => setCat(c)} className={`rounded-full border px-2.5 py-1 ${cat === c ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-stone-300 bg-white'}`}>{LABEL[c] ?? c}</button>
        ))}
      </div>

      <div className="rounded-lg border border-stone-200 bg-white p-3 text-xs">
        <div className="mb-1 flex flex-wrap items-center gap-3">
          <span className="font-semibold uppercase tracking-wide text-stone-500">Months</span>
          <span className="font-mono">{data.months[stats.lo]} → {data.months[stats.hi]}</span>
          <span className="text-stone-500">({stats.monthsN} month{stats.monthsN > 1 ? 's' : ''}, {stats.total.toLocaleString()} located requests in window)</span>
          <button type="button" className="underline" onClick={() => setRange(null)}>reset</button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <label className="flex items-center gap-2">from
            <input type="range" min={0} max={data.months.length - 1} value={stats.lo} aria-label="First month" className="w-full"
              onChange={(e) => { const v = Number(e.target.value); setRange([Math.min(v, stats.hi), stats.hi]) }} />
          </label>
          <label className="flex items-center gap-2">to
            <input type="range" min={0} max={data.months.length - 1} value={stats.hi} aria-label="Last month" className="w-full"
              onChange={(e) => { const v = Number(e.target.value); setRange([stats.lo, Math.max(v, stats.lo)]) }} />
          </label>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-lg border border-stone-200 bg-white p-3">
          <h3 className="mb-2 text-sm font-semibold">By category</h3>
          <table className="w-full text-sm">
            <tbody>
              {stats.byCat.map(([c, n]) => (
                <tr key={c} className="border-t border-stone-100">
                  <td className="py-1 pr-2">{LABEL[c] ?? c}</td>
                  <td className="py-1 text-right font-mono">{n.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <details className="mt-2 text-xs text-stone-500">
            <summary>How the city's "Service Type" (+ "Category") maps into these categories (hand-filled, data/taxonomy_311.csv)</summary>
            <ul className="mt-1 list-disc pl-4">
              {data.taxonomy.map((r, i) => (<li key={i}>{r.service_type}{r.category_raw !== '*' ? ` / ${r.category_raw}` : ''} → {LABEL[r.category] ?? r.category}</li>))}
            </ul>
          </details>
        </section>

        <section className="rounded-lg border border-stone-200 bg-white p-3">
          <h3 className="mb-2 text-sm font-semibold">By month</h3>
          <ol className="space-y-1 text-xs">
            {stats.byMonth.map(([m, n]) => (
              <li key={m} className="flex items-center gap-2">
                <span className="w-16 font-mono text-stone-600">{m}</span>
                <span className="h-3 rounded bg-indigo-500" style={{ width: `${(n / stats.monthMax) * 100}%` }} aria-hidden />
                <span className="font-mono">{n.toLocaleString()}</span>
              </li>
            ))}
          </ol>
        </section>
      </div>

      <section className="rounded-lg border border-stone-200 bg-white p-3">
        <h3 className="mb-2 text-sm font-semibold">Top 20 tracts — by volume and by annualized rate per 1,000 residents</h3>
        <div className="grid gap-4 text-xs md:grid-cols-2">
          <ol className="space-y-1">
            {stats.tracts.slice(0, 20).map(([t, n], i) => (
              <li key={t} className="flex items-center gap-2">
                <span className="w-5 text-right text-stone-400">{i + 1}</span>
                <span className="w-28 font-mono">{t}</span>
                <span className="h-3 rounded bg-emerald-500" style={{ width: `${(n / stats.tractMax) * 55}%` }} aria-hidden />
                <span className="font-mono">{n.toLocaleString()}</span>
              </li>
            ))}
          </ol>
          <ol className="space-y-1">
            {stats.byRate.slice(0, 20).map(([t, n, r], i) => (
              <li key={t} className="flex items-center gap-2">
                <span className="w-5 text-right text-stone-400">{i + 1}</span>
                <span className="w-28 font-mono">{t}</span>
                <span className="h-3 rounded bg-violet-500" style={{ width: `${((r ?? 0) / (stats.byRate[0]?.[2] ?? 1)) * 55}%` }} aria-hidden />
                <span className="font-mono">{Math.round(r ?? 0)}/1k</span>
                <span className="text-stone-400">({n.toLocaleString()} req, pop {data.population[t]?.toLocaleString()})</span>
              </li>
            ))}
          </ol>
        </div>
        <p className="mt-2 text-xs text-stone-500">Rate = requests ÷ ACS 2024 tract population × 1,000, scaled to 12 months. The "problems without voice" ranking (high 311, low comment volume) arrives with the fairness step.</p>
      </section>

      {sample && (
        <section className="rounded-lg border border-stone-200 bg-white p-3">
          <h3 className="mb-1 text-sm font-semibold">Sample rows (inspector)</h3>
          <p className="mb-2 text-xs text-stone-500">{sample.note}</p>
          <div className="max-h-72 overflow-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-stone-100 text-left"><tr><th className="p-1">id</th><th className="p-1">month</th><th className="p-1">service type</th><th className="p-1">city category</th><th className="p-1">our category</th><th className="p-1">status</th><th className="p-1">source</th><th className="p-1">tract</th><th className="p-1">district</th></tr></thead>
              <tbody>
                {sample.rows.map((r) => (
                  <tr key={r.request_id} className="border-t border-stone-100">
                    <td className="p-1 font-mono">{r.request_id}</td><td className="p-1">{r.month}</td><td className="p-1">{r.category_raw}</td><td className="p-1">{r.subcategory_raw ?? '—'}</td><td className="p-1">{LABEL[r.category] ?? r.category}</td><td className="p-1">{r.status}</td><td className="p-1">{r.source}</td><td className="p-1 font-mono">{r.tract_id}</td><td className="p-1">{r.council_district ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}
