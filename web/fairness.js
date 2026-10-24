/**
 * Client-side fairness math for drawn regions. Dependency-free ES module; mirrors scripts/fairness.py.
 * Parity with AIF360 is asserted by web/fairness.test.mjs against public/data/fairness/parity_fixtures.json.
 *
 * Tract records: { tract_id, population, voice_count, problems_count, voice_rate, problems_rate,
 *                  low_income, majority_nonwhite, renter_majority, high_lep }  (attribute 1 = privileged, 0 = unprivileged)
 * Families never mix: voice and requests_311 are measured separately and returned under separate keys.
 * The outcome median is the CITYWIDE one passed in (from meta.json); it is never recomputed for a region.
 */

export const MIN_REGION_TRACTS = 5
export const MIN_GROUP_TRACTS = 2
export const MIN_REGION_VOICE = 10

/** Citywide percentile rank (0-100) = share of tracts strictly below: 100 * below / n. Identical to src/data/families.ts. */
export function percentileRanks(rates) {
  const vals = Object.values(rates).filter((v) => v !== null && Number.isFinite(v)).sort((a, b) => a - b)
  const n = vals.length
  const out = {}
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
    out[k] = (100 * lo) / n
  }
  return out
}

function weightOf(t, i, weights) {
  if (weights === undefined || weights === null) return 1
  if (weights === 'population') return Number(t.population) || 0
  if (typeof weights === 'function') return weights(t, i)
  return weights[i]
}

/**
 * DI = P(fav|unpriv)/P(fav|priv), SPD = P(fav|unpriv) - P(fav|priv); favorable = rate > cityMedian.
 * opts.weights: undefined (each tract one unit) | 'population' | number[] | (tract, i) => number.
 * opts.rateKey: field holding the per-1k rate (default 'rate').
 */
export function measure(tracts, attr, cityMedian, opts = {}) {
  const rateKey = opts.rateKey ?? 'rate'
  const g = { 1: { n: 0, favorable: 0, weight: 0, weightFavorable: 0 }, 0: { n: 0, favorable: 0, weight: 0, weightFavorable: 0 } }
  tracts.forEach((t, i) => {
    const a = t[attr]
    const r = t[rateKey]
    if ((a !== 0 && a !== 1) || r === null || r === undefined || !Number.isFinite(r)) return
    const fav = r > cityMedian ? 1 : 0
    const w = weightOf(t, i, opts.weights)
    g[a].n += 1
    g[a].favorable += fav
    g[a].weight += w
    g[a].weightFavorable += w * fav
  })
  const rate = (x) => (x.weight > 0 ? x.weightFavorable / x.weight : null)
  const p = rate(g[1])
  const u = rate(g[0])
  const empty = g[1].n === 0 || g[0].n === 0
  return {
    di: empty || p === null || u === null || p === 0 ? null : u / p,
    spd: empty || p === null || u === null ? null : u - p,
    privileged: { n: g[1].n, favorable: g[1].favorable, weight: g[1].weight, baseRate: p },
    unprivileged: { n: g[0].n, favorable: g[0].favorable, weight: g[0].weight, baseRate: u },
  }
}

/**
 * expected = population_share * total voice, gap = (expected - observed) / expected (null when expected is 0).
 * opts.totalPopulation / opts.totalVoice default to the sums over `tracts`; pass citywide totals to keep shares citywide.
 */
export function participationGap(tracts, opts = {}) {
  const countKey = opts.countKey ?? 'voice_count'
  const pop = opts.totalPopulation ?? tracts.reduce((s, t) => s + (Number(t.population) || 0), 0)
  const total = opts.totalVoice ?? tracts.reduce((s, t) => s + (Number(t[countKey]) || 0), 0)
  return tracts.map((t) => {
    const share = pop > 0 ? (Number(t.population) || 0) / pop : 0
    const expected = share * total
    const observed = Number(t[countKey]) || 0
    return { tract_id: t.tract_id, population_share: share, expected, observed, gap: expected > 0 ? (expected - observed) / expected : null }
  })
}

/**
 * Region summary with the not_enough_data rule: < 5 tracts, either group < 2 tracts, or voice count < 10.
 * cityMedian = { voice, problems } (citywide, from meta.json).
 */
export function regionSummary(tracts, { attr = 'low_income', cityMedian } = {}) {
  if (!cityMedian || typeof cityMedian.voice !== 'number' || typeof cityMedian.problems !== 'number') {
    throw new Error('regionSummary needs the citywide medians { voice, problems }; they are never recomputed per region')
  }
  const nPriv = tracts.filter((t) => t[attr] === 1).length
  const nUnpriv = tracts.filter((t) => t[attr] === 0).length
  const voiceCount = tracts.reduce((s, t) => s + (Number(t.voice_count) || 0), 0)
  const problemsCount = tracts.reduce((s, t) => s + (Number(t.problems_count) || 0), 0)
  const counts = {
    n_tracts: tracts.length,
    groups: { privileged: nPriv, unprivileged: nUnpriv },
    voice: { count: voiceCount },
    requests_311: { count: problemsCount },
  }
  const reasons = []
  if (tracts.length < MIN_REGION_TRACTS) reasons.push(`fewer than ${MIN_REGION_TRACTS} tracts`)
  if (nPriv < MIN_GROUP_TRACTS || nUnpriv < MIN_GROUP_TRACTS) reasons.push(`a group has fewer than ${MIN_GROUP_TRACTS} tracts`)
  if (voiceCount < MIN_REGION_VOICE) reasons.push(`fewer than ${MIN_REGION_VOICE} voice comments`)
  const base = { attribute: attr, city_median_rate_per_1k: { ...cityMedian }, counts }
  if (reasons.length) return { ...base, not_enough_data: true, reasons }
  const fam = (median, rateKey) => ({
    unweighted: measure(tracts, attr, median, { rateKey }),
    population_weighted: measure(tracts, attr, median, { rateKey, weights: 'population' }),
  })
  return {
    ...base,
    not_enough_data: false,
    voice: { family: 'voice', count: voiceCount, ...fam(cityMedian.voice, 'voice_rate') },
    requests_311: { family: 'problems', count: problemsCount, ...fam(cityMedian.problems, 'problems_rate') },
  }
}
