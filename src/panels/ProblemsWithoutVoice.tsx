import { useMemo } from 'react'
import type { RawComment } from '../data/types'
import type { Requests311ByTract } from '../data/types311'
import { PROBLEM_PCT_MIN, VOICE_PCT_MAX, percentileRanks, problemsWithoutVoice, ratePer1k } from '../data/families'

/**
 * "Problems without voice": tracts in the top 30% of 311 reporting per resident and the bottom 30% of
 * written comment per resident. Compared by citywide percentile only; raw counts are never shown side by side.
 */
export default function ProblemsWithoutVoice({ data311, voice }: { data311: Requests311ByTract; voice: RawComment[] }) {
  const result = useMemo(() => {
    const problemRates: Record<string, number | null> = {}
    for (const t of Object.keys(data311.population)) problemRates[t] = ratePer1k(data311.totals[t] ?? 0, data311.population[t], data311.months_covered)
    const problemPct = percentileRanks(problemRates)

    const located = voice.filter((c) => c.tract_id)
    if (located.length === 0) return { problemPct, voicePct: null, rows: [], located: 0 }
    const counts: Record<string, number> = {}
    for (const c of located) counts[c.tract_id as string] = (counts[c.tract_id as string] ?? 0) + 1
    const voiceRates: Record<string, number | null> = {}
    for (const t of Object.keys(data311.population)) voiceRates[t] = ratePer1k(counts[t] ?? 0, data311.population[t])
    const voicePct = percentileRanks(voiceRates)
    return { problemPct, voicePct, rows: problemsWithoutVoice(problemPct, voicePct), located: located.length }
  }, [data311, voice])

  const highProblem = Object.entries(result.problemPct)
    .filter(([, p]) => p !== null && p >= PROBLEM_PCT_MIN)
    .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))

  return (
    <section className="rounded-lg border border-violet-200 bg-white p-3">
      <h3 className="text-sm font-semibold">Problems without voice</h3>
      <p className="mb-2 text-xs text-stone-600">
        Tracts at or above the {PROBLEM_PCT_MIN}th percentile of 311 requests per 1,000 residents and at or below the {VOICE_PCT_MAX}th percentile of written comments per 1,000
        residents. Both families are ranked separately across all tracts; only the two percentiles are compared, never the raw counts.
      </p>

      {result.voicePct === null ? (
        <>
          <div className="mb-2 rounded-md border border-dashed border-stone-300 bg-stone-50 p-2 text-xs text-stone-700">
            Voice percentiles are pending: none of the {voice.length} letters has been located to a tract yet. That happens in the location-resolution step. Until then this lists
            the {highProblem.length} tracts that meet the 311 side of the rule, with the voice column left empty.
          </div>
          <PctTable rows={highProblem.slice(0, 25).map(([t, p]) => ({ tract_id: t, problem_pct: p as number, voice_pct: null }))} />
        </>
      ) : result.rows.length === 0 ? (
        <div className="rounded-md border border-dashed border-stone-300 p-3 text-center text-xs text-stone-500">No tract meets both thresholds with the data loaded.</div>
      ) : (
        <>
          <p className="mb-1 text-xs text-stone-500">{result.rows.length} tracts meet both thresholds ({result.located} letters located so far).</p>
          <PctTable rows={result.rows} />
        </>
      )}
    </section>
  )
}

function PctTable({ rows }: { rows: { tract_id: string; problem_pct: number; voice_pct: number | null }[] }) {
  return (
    <div className="max-h-80 overflow-auto">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-stone-100 text-left">
          <tr>
            <th className="p-1">tract</th>
            <th className="p-1">311 percentile (problems)</th>
            <th className="p-1">comment percentile (voice)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.tract_id} className="border-t border-stone-100">
              <td className="p-1 font-mono">{r.tract_id}</td>
              <td className="p-1">
                <span className="inline-block h-2 rounded bg-emerald-500 align-middle" style={{ width: `${r.problem_pct * 0.8}px` }} aria-hidden /> <span className="font-mono">{r.problem_pct.toFixed(0)}</span>
              </td>
              <td className="p-1">
                {r.voice_pct === null ? <span className="text-stone-400">pending</span> : (
                  <><span className="inline-block h-2 rounded bg-indigo-500 align-middle" style={{ width: `${r.voice_pct * 0.8}px` }} aria-hidden /> <span className="font-mono">{r.voice_pct.toFixed(0)}</span></>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
