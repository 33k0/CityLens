import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { measure, participationGap, percentileRanks, regionSummary } from './fairness.js'
import { percentileRanks as tsPercentileRanks } from '../src/data/families.ts'

const read = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url), 'utf8'))
const FX = read('../public/data/fairness/parity_fixtures.json')
const FAM = read('../tests/fixtures/families_parity.json')
const TOL = 1e-9

const close = (a, b) => (a === null || b === null ? a === b : Math.abs(a - b) <= TOL)
const FAMILIES = { voice: 'voice_rate', problems: 'problems_rate' }

describe('web/fairness.js matches AIF360 (parity_fixtures.json)', () => {
  for (const [family, rateKey] of Object.entries(FAMILIES)) {
    for (const attr of FX.attributes) {
      for (const weighting of ['unweighted', 'population_weighted']) {
        it(`${family} ${attr} ${weighting}`, () => {
          const exp = FX.expected[family][attr][weighting]
          const got = measure(FX.tracts, attr, FX.city_median_rate_per_1k[family], {
            rateKey,
            weights: weighting === 'population_weighted' ? 'population' : undefined,
          })
          expect(close(got.di, exp.di), `di ${got.di} vs ${exp.di}`).toBe(true)
          expect(close(got.spd, exp.spd), `spd ${got.spd} vs ${exp.spd}`).toBe(true)
          expect(got.privileged.n).toBe(exp.privileged.n)
          expect(got.privileged.favorable).toBe(exp.privileged.favorable)
          expect(got.unprivileged.n).toBe(exp.unprivileged.n)
          expect(got.unprivileged.favorable).toBe(exp.unprivileged.favorable)
        })
      }
    }
  }
})

describe('regionSummary', () => {
  const byId = Object.fromEntries(FX.tracts.map((t) => [t.tract_id, t]))
  for (const r of FX.regions) {
    it(`region ${r.name}: not_enough_data=${r.not_enough_data}, metrics match python`, () => {
      const got = regionSummary(r.tract_ids.map((id) => byId[id]), { attr: r.attr, cityMedian: FX.city_median_rate_per_1k })
      expect(got.not_enough_data).toBe(r.not_enough_data)
      if (!r.not_enough_data) {
        for (const key of ['voice', 'requests_311']) {
          for (const w of ['unweighted', 'population_weighted']) {
            expect(close(got[key][w].di, r[key][w].di)).toBe(true)
            expect(close(got[key][w].spd, r[key][w].spd)).toBe(true)
          }
        }
      } else {
        expect(got.voice).toBeUndefined()
        expect(got.counts.n_tracts).toBe(r.tract_ids.length)
      }
    })
  }

  const ok = (n, priv, voice) =>
    Array.from({ length: n }, (_, i) => ({ tract_id: `x${i}`, population: 1000, low_income: i < priv ? 1 : 0, voice_count: voice / n, problems_count: 5, voice_rate: 1, problems_rate: 1 }))
  it('triggers on < 5 tracts', () => expect(regionSummary(ok(4, 2, 40), { cityMedian: { voice: 0, problems: 0 } }).not_enough_data).toBe(true))
  it('triggers on a group with < 2 tracts', () => expect(regionSummary(ok(6, 1, 40), { cityMedian: { voice: 0, problems: 0 } }).not_enough_data).toBe(true))
  it('triggers on < 10 voice comments', () => expect(regionSummary(ok(6, 3, 9), { cityMedian: { voice: 0, problems: 0 } }).not_enough_data).toBe(true))
  it('passes when all thresholds are met', () => expect(regionSummary(ok(6, 3, 10), { cityMedian: { voice: 0, problems: 0 } }).not_enough_data).toBe(false))
  it('requires the citywide medians', () => expect(() => regionSummary(ok(6, 3, 10), {})).toThrow())
  it('keeps families under separate keys', () => {
    const r = regionSummary(ok(6, 3, 10), { cityMedian: { voice: 0, problems: 0 } })
    expect(r.voice.family).toBe('voice')
    expect(r.requests_311.family).toBe('problems')
    expect(r.counts.voice.count).toBe(10)
    expect(r.counts.requests_311.count).toBe(30)
  })
})

describe('participationGap', () => {
  it('matches python gaps', () => {
    const got = participationGap(FX.tracts)
    FX.gaps.forEach((g, i) => {
      expect(got[i].tract_id).toBe(g.tract_id)
      expect(close(got[i].expected, g.expected)).toBe(true)
      expect(close(got[i].gap, g.gap)).toBe(true)
    })
  })
})

describe('percentileRanks parity', () => {
  it('matches tests/fixtures/families_parity.json', () => {
    const got = percentileRanks(FAM.rates)
    for (const [k, v] of Object.entries(FAM.expected_pct)) expect(close(got[k], v)).toBe(true)
  })
  it('is identical to src/data/families.ts', () => {
    expect(percentileRanks(FAM.rates)).toEqual(tsPercentileRanks(FAM.rates))
  })
})
