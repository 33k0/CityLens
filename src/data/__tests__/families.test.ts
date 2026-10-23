import { describe, expect, it } from 'vitest'
import fixture from '../../../tests/fixtures/families_parity.json'
import { percentileRanks, problemsWithoutVoice, ratePer1k, sharesWithinFamily, sumWithinFamily } from '../families'

describe('channel separation', () => {
  it('sums within a family', () => {
    expect(sumWithinFamily('voice', [{ channel: 'letter', n: 3 }, { channel: 'email', n: 2 }, { channel: 'site', n: 1 }])).toBe(6)
    expect(sumWithinFamily('problems', [{ channel: '311', n: 40 }])).toBe(40)
  })
  it('refuses to add 311 into voice, or voice into problems', () => {
    expect(() => sumWithinFamily('voice', [{ channel: 'letter', n: 3 }, { channel: '311', n: 2300 }])).toThrow(/channel separation/)
    expect(() => sumWithinFamily('problems', [{ channel: '311', n: 1 }, { channel: 'site', n: 1 }])).toThrow(/channel separation/)
  })
  it('computes shares within one family only', () => {
    const s = sharesWithinFamily('voice', [
      { channel: 'letter', n: 3, category: 'housing' },
      { channel: 'email', n: 1, category: 'transportation' },
    ])
    expect(s).toEqual({ housing: 0.75, transportation: 0.25 })
    expect(() => sharesWithinFamily('voice', [{ channel: '311', n: 1, category: 'x' }])).toThrow()
  })
})

describe('rates and percentiles', () => {
  it('annualizes per-1k rates', () => {
    expect(ratePer1k(50, 1000, 12)).toBe(50)
    expect(ratePer1k(50, 1000, 6)).toBe(100)
    expect(ratePer1k(5, 0)).toBeNull()
  })
  it('mid-ranks ties and skips nulls', () => {
    const p = percentileRanks({ a: 0, b: 0, c: 10, d: 20, e: null })
    expect(p).toEqual({ a: 25, b: 25, c: 62.5, d: 87.5, e: null })
  })
  it('flags problems without voice by percentile only', () => {
    const rows = problemsWithoutVoice({ a: 90, b: 75, c: 50, d: 95 }, { a: 10, b: 30, c: 0, d: 40 })
    expect(rows.map((r) => r.tract_id)).toEqual(['a', 'b'])
  })
  it('matches the Python implementation on the shared fixture', () => {
    const got = percentileRanks(fixture.rates as Record<string, number | null>)
    for (const [k, v] of Object.entries(fixture.expected_pct)) {
      if (v === null) expect(got[k]).toBeNull()
      else expect(got[k]).toBeCloseTo(v as number, 9)
    }
    const gaps = problemsWithoutVoice(fixture.problem_pct as Record<string, number>, fixture.voice_pct as Record<string, number>)
    expect(gaps.map((g) => g.tract_id)).toEqual(fixture.expected_gaps)
  })
})
