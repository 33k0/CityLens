/**
 * Channel separation rule.
 * Voice = letters + email + site. Problems = 311. The two families are never summed, pooled, or ranked
 * together. Cross-family comparison goes through citywide percentiles of per-1k-resident rates only.
 * scripts/families.py mirrors these functions for the build-time fairness step; tests keep them in parity.
 */
export type Family = 'voice' | 'problems'
export type Channel = 'letter' | 'email' | 'site' | '311'

export const FAMILY_OF: Record<Channel, Family> = { letter: 'voice', email: 'voice', site: 'voice', '311': 'problems' }
export const FAMILY_LABEL: Record<Family, string> = { voice: 'What residents said', problems: 'What residents reported to 311' }

/** Thresholds for "problems without voice". */
export const PROBLEM_PCT_MIN = 70
export const VOICE_PCT_MAX = 30

export interface Counted {
  channel: Channel
  n: number
}

/** Sum counts that all belong to one family. Throws if any item is from the other family. */
export function sumWithinFamily(family: Family, items: Counted[]): number {
  let total = 0
  for (const it of items) {
    if (FAMILY_OF[it.channel] !== family) {
      throw new Error(`channel separation: refusing to add a ${it.channel} count (${FAMILY_OF[it.channel]}) into ${family}`)
    }
    total += it.n
  }
  return total
}

/** Shares within one family only (category -> share of that family's total). */
export function sharesWithinFamily(family: Family, rows: (Counted & { category: string })[]): Record<string, number> {
  const total = sumWithinFamily(family, rows)
  const out: Record<string, number> = {}
  if (!total) return out
  for (const r of rows) out[r.category] = (out[r.category] ?? 0) + r.n / total
  return out
}

/** Annualized rate per 1,000 residents. Tracts without population get null. */
export function ratePer1k(count: number, population: number | undefined, monthsCovered = 12): number | null {
  if (!population || population <= 0) return null
  return (count / population) * 1000 * (12 / Math.max(1, monthsCovered))
}

/**
 * Citywide percentile rank (0-100) with mid-rank ties: 100 * (below + 0.5 * equal) / n.
 * Null rates are excluded from the ranking and come back null.
 */
export function percentileRanks(rates: Record<string, number | null>): Record<string, number | null> {
  const vals = Object.values(rates).filter((v): v is number => v !== null && Number.isFinite(v)).sort((a, b) => a - b)
  const n = vals.length
  const out: Record<string, number | null> = {}
  for (const [k, v] of Object.entries(rates)) {
    if (v === null || !Number.isFinite(v) || n === 0) {
      out[k] = null
      continue
    }
    let lo = 0
    let hi = n
    while (lo < hi) {
      const mid = (lo + hi) >> 1
      if (vals[mid] < v) lo = mid + 1
      else hi = mid
    }
    const below = lo
    let equal = 0
    while (below + equal < n && vals[below + equal] === v) equal++
    out[k] = (100 * (below + 0.5 * equal)) / n
  }
  return out
}

export interface GapRow {
  tract_id: string
  problem_pct: number
  voice_pct: number
}

/**
 * Tracts with problem_pct >= 70 and voice_pct <= 30, sorted by the widest gap first.
 * Both inputs must already be percentiles of per-1k rates; raw counts are never accepted here.
 */
export function problemsWithoutVoice(problemPct: Record<string, number | null>, voicePct: Record<string, number | null>): GapRow[] {
  const rows: GapRow[] = []
  for (const [t, p] of Object.entries(problemPct)) {
    const v = voicePct[t]
    if (p === null || v === null || v === undefined) continue
    if (p >= PROBLEM_PCT_MIN && v <= VOICE_PCT_MAX) rows.push({ tract_id: t, problem_pct: p, voice_pct: v })
  }
  return rows.sort((a, b) => b.problem_pct - b.voice_pct - (a.problem_pct - a.voice_pct) || a.tract_id.localeCompare(b.tract_id))
}
