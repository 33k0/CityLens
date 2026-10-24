import { describe, it, expect, vi, afterEach } from 'vitest'
import { askAssistant, retrieve, sanitize, searchAnswer, stem } from '../assistant.js'
import { parseAnswer, validate, validateActions, buildPrompt } from '../../../server/assistant.mjs'

const C = [
  { id: 'Ed0eb2b84', subject: 'Half of King Road is pitch black at night', text: 'For almost a month now the streetlights along King Road between Story and Tully have been out.', section: 'Streets & Infrastructure', subsection: 'Streetlight outage', stance: 'support', lang: 'en', mock: true, nbhd: 'East Side', tract: '06085503504' },
  { id: 'E96b885ff', subject: 'potholes on Senter', text: 'The pavement on Senter is crumbling and full of potholes.', section: 'Streets & Infrastructure', subsection: 'Pavement', stance: 'oppose', lang: 'en', mock: true, nbhd: 'Seven Trees', tract: '06085503602' },
  { id: 'L41a0f758', subject: 'RV parking item 2.8', text: 'No one on the council has the legal authority to waive state vehicular laws for the Berryessa RV lot.', section: 'Housing & Affordability Policy', subsection: 'Homelessness', stance: 'oppose', lang: 'en', mock: false, nbhd: 'Berryessa', tract: '06085504400' },
  { id: 'L02df713e', subject: 'Protect immigrant residents', text: 'Please keep San José a sanctuary city and limit cooperation with ICE.', section: 'Governance & Civic Rights', subsection: 'Immigration', stance: 'support', lang: 'en', mock: false, nbhd: 'Downtown', tract: '06085500100' },
  { id: 'E15c5d688', subject: 'Illegal dumping', text: 'Someone keeps leaving mattresses and garbage behind the store.', section: 'Sanitation & Environmental Quality', subsection: 'Illegal dumping', stance: 'neutral', lang: 'en', mock: true, nbhd: 'Alum Rock', tract: '06085503700' },
  { id: 'Edupe0001', subject: 'Illegal dumping', text: 'Someone keeps leaving mattresses and garbage behind the store.', section: 'Sanitation & Environmental Quality', subsection: 'Illegal dumping', stance: 'neutral', lang: 'en', mock: true, nbhd: 'Alum Rock', tract: '06085503700' },
]
const VENDOR = /granite|ollama|\bibm\b|claude|\bbob\b/i

afterEach(() => vi.unstubAllGlobals())

describe('retrieval', () => {
  it('stems simply', () => {
    expect(stem('streetlights')).toBe('streetlight')
    expect(stem('potholes')).toBe('pothole')
    expect(stem('king')).toBe('king')
  })
  it('ranks the streetlight comment first for "dark streets near King Road"', () => {
    expect(retrieve('dark streets near King Road', C, 12)[0].id).toBe('Ed0eb2b84')
  })
  it('uses civic synonyms', () => {
    expect(retrieve('lights out', C)[0].id).toBe('Ed0eb2b84')
    expect(retrieve('road condition', C).map(c => c.id)).toContain('E96b885ff')
    expect(retrieve('trash', C)[0].id).toBe('E15c5d688')
    expect(retrieve('ICE deportations', C)[0].id).toBe('L02df713e')
  })
  it('dedupes identical text and returns nothing for unrelated words', () => {
    const ids = retrieve('dumping garbage', C).map(c => c.id)
    expect(ids.filter(i => i === 'E15c5d688' || i === 'Edupe0001')).toHaveLength(1)
    expect(retrieve('zeppelin', C)).toEqual([])
  })
})

describe('sanitize', () => {
  it('strips unknown ids and keeps valid ones and refs', () => {
    const r = sanitize('Lights are out [[Ed0eb2b84]][[FAKE123]] and [[E96b885ff, Lnope]] per [[metric:H5]] [[metric:H99]].', ['Ed0eb2b84', 'E96b885ff'], ['metric:H5'])
    expect(r.text).toBe('Lights are out [[Ed0eb2b84]] and [[E96b885ff]] per [[metric:H5]].')
    expect(r.cited).toEqual(['Ed0eb2b84', 'E96b885ff'])
    expect(r.refs).toEqual(['metric:H5'])
  })
  it('upgrades bare [ID] and scrubs vendor names', () => {
    const r = sanitize('Granite says via Ollama and Bob: dark [Ed0eb2b84].', ['Ed0eb2b84'])
    expect(r.text).toContain('[[Ed0eb2b84]]')
    expect(r.text).not.toMatch(VENDOR)
  })
})

describe('askAssistant', () => {
  it('falls back to search when fetch rejects, citing only in-scope ids', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    const res = await askAssistant({ question: 'dark streets near King Road', scopeLabel: 'East Side', sectionTitle: 'All sections', comments: C })
    expect(res.engine).toBe('search')
    expect(res.cited.length).toBeGreaterThan(0)
    const ids = new Set(C.map(c => c.id))
    res.cited.forEach(id => expect(ids.has(id)).toBe(true))
    expect(res.text).toMatch(/simulated email/)
    expect(res.text + (res.note || '')).not.toMatch(VENDOR)
    expect(res.actions).toEqual([])
  })
  it('falls back on non-2xx and returns a note when nothing matches', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({}) }))
    const res = await askAssistant({ question: 'zeppelin landing pads', scopeLabel: 'Alviso', comments: C })
    expect(res).toMatchObject({ text: '', cited: [], engine: 'search' })
    expect(res.note).toMatch(/No comments in Alviso mention/)
  })
  it('answers count questions from numbers deterministically, never blending families', async () => {
    const res = searchAnswer({ question: 'How many 311 reports and comments are there?', scopeLabel: 'All of San José', comments: C, numbers: { voice: { comments: 435 }, requests_311: { reports: 217415 } } })
    expect(res.text).toMatch(/Letters and emails.*435/)
    expect(res.text).toMatch(/311 problem reports.*217,415/)
    expect(res.text).toMatch(/not added together/)
  })
  it('passes through assistant answers, stripping out-of-scope ids and keeping refs/actions', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ text: 'Residents report outages [[Ed0eb2b84]][[Lzzzzzzzz]] see [[metric:H5]].', cited: ['Ed0eb2b84'], refs: ['metric:H5'], actions: [{ type: 'set_scheme', id: 'prob' }, { type: 'rm_rf' }], engine: 'assistant' }) })
    vi.stubGlobal('fetch', fetchMock)
    const res = await askAssistant({ question: 'dark streets', scopeLabel: 'East Side', comments: C, regionTracts: ['06085503504'] })
    expect(res.engine).toBe('assistant')
    expect(res.cited).toEqual(['Ed0eb2b84'])
    expect(res.refs).toEqual(['metric:H5'])
    expect(res.actions).toEqual([{ type: 'set_scheme', id: 'prob' }])
    expect(res.text).not.toContain('Lzzzzzzzz')
    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body.context[0]).toMatchObject({ id: 'Ed0eb2b84', simulated: true, place: 'East Side' })
    expect(body.regionTracts).toEqual(['06085503504'])
  })
})

describe('server validation', () => {
  it('parses fenced / prose-wrapped JSON and repairs inner quotes', () => {
    expect(parseAnswer('Here:\n```json\n{"answer":"ok [[x]]","cited_ids":["x"],"cited_refs":[]}\n```').answer).toBe('ok [[x]]')
    const p = parseAnswer('{"answer":"They called it "patch and pray" [[E96b885ff]]","cited_ids":["E96b885ff"],"cited_refs":[]}')
    expect(p.answer).toBe('They called it "patch and pray" [[E96b885ff]]')
  })
  it('drops unknown ids, keeps real ones, 422s uncited claims', () => {
    const ok = validate({ answer: 'Story Road lights failed again [[E96b885ff]][[Enotreal1]] [[metric:H5]] [[metric:ZZ]]', cited_ids: [], cited_refs: [], actions: [] }, 'what about streetlights')
    expect(ok.status).toBe(200)
    expect(ok.body.cited).toEqual(['E96b885ff'])
    expect(ok.body.refs).toEqual(['metric:H5'])
    expect(validate({ answer: 'Residents are furious about lights.', cited_ids: ['nope'], cited_refs: [], actions: [] }, 'what about streetlights').status).toBe(422)
  })
  it('validates actions against the allow-list and app data', () => {
    const a = validateActions([{ type: 'set_scheme', id: 'gap' }, { type: 'zoom_tract', id: '00000000000' }, { type: 'open_comment', id: 'E96b885ff' }, { type: 'filter_stance', ids: ['oppose', 'angry'] }, { type: 'delete_all' }])
    expect(a).toEqual([{ type: 'set_scheme', id: 'gap' }, { type: 'open_comment', id: 'E96b885ff' }, { type: 'filter_stance', ids: ['oppose'] }])
  })
  it('prompt carries scope and head start', () => {
    const p = buildPrompt({ question: 'q', scopeLabel: 'East Side', sectionTitle: 'All sections', regionTracts: ['06085503504'], context: [{ id: 'Ed0eb2b84', simulated: true, text: 't' }] })
    expect(p).toContain('app-analyst')
    expect(p).toContain('06085503504')
    expect(p).toContain('[Ed0eb2b84] SIMULATED email')
  })
})
