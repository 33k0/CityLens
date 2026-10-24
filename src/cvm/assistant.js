/* CityLens staff assistant — browser client.
   Retrieval (BM25 over in-scope comments) + POST /api/assistant (dev bridge to a local model).
   When the bridge is missing (static build), errors, or times out, a keyword-search summary is
   built locally from the retrieved comments only. No dependencies. */

const STOP = new Set(('a an and are as at be been being but by can could did do does doing for from had has have having he her here hers him his how i if in into is it its just me more most my no nor not of off on once only or other our ours out over own same she should so some such than that the their theirs them then there these they this those through to too under until up very was we were what when where which while who whom why will with would you your yours about above after again against all am any because before below between both down during each few further let ll re s t ve also get got im ive dont please thank thanks dear hello hi council councilmember city san jose sincerely regards').split(' '))

export function stem(w) {
  if (w.length <= 3) return w
  if (w.endsWith('ies') && w.length > 4) return w.slice(0, -3) + 'y'
  if (w.endsWith('sses')) return w.slice(0, -2)
  if (/(?:s|x|z|ch|sh)es$/.test(w) && w.length > 4) return w.slice(0, -2)
  if (w.endsWith('ing') && w.length - 3 >= 3) return w.slice(0, -3)
  if (w.endsWith('ed') && w.length - 2 >= 3) return w.slice(0, -2)
  if (w.endsWith('s') && !w.endsWith('ss') && !w.endsWith('us') && !w.endsWith('is')) return w.slice(0, -1)
  return w
}

export function tokenize(s) {
  const out = []
  const words = String(s || '').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '')
    .replace(/street\s+lights?/g, 'streetlight').replace(/pot\s+holes?/g, 'pothole')
    .match(/[a-z0-9]+/g) || []
  for (const w of words) { if (!STOP.has(w) && w.length > 1) out.push(stem(w)) }
  return out
}

/* civic synonym groups (stemmed): a query term in a group also matches the others, at reduced weight */
const SYN_GROUPS = [
  ['streetlight', 'light', 'dark', 'lamp', 'lit', 'blackout'],
  ['pothole', 'pavement', 'road', 'repav', 'asphalt'],
  ['dump', 'trash', 'garbage', 'debri', 'litter', 'junk'],
  ['rent', 'rental', 'tenant', 'landlord', 'evict', 'lease'],
  ['police', 'patrol', 'crime', 'safety', 'safe', 'officer', 'sjpd'],
  ['immigrant', 'immigration', 'ice', 'sanctuary', 'deport', 'undocument'],
].map(g => g.map(stem))
const SYN = new Map()
for (const g of SYN_GROUPS) for (const t of g) SYN.set(t, [...new Set([...(SYN.get(t) || []), ...g.filter(x => x !== t)])])

function expandQuery(q) {
  const w = new Map()
  for (const t of tokenize(q)) w.set(t, Math.max(w.get(t) || 0, 1))
  for (const t of [...w.keys()]) for (const s of SYN.get(t) || []) if (!w.has(s)) w.set(s, 0.6)
  return w
}

const docText = c => [c.subject, c.text, c.section, c.subsection].filter(Boolean).join(' \n ')
const normText = s => String(s || '').toLowerCase().replace(/\s+/g, ' ').trim()

/* BM25 (k1 1.2, b 0.75). Returns [{c, score}] sorted, score > 0, identical texts deduped. */
export function rank(question, comments) {
  const q = expandQuery(question)
  if (!q.size || !comments?.length) return []
  const docs = comments.map(c => { const toks = tokenize(docText(c)); const tf = new Map(); toks.forEach(t => tf.set(t, (tf.get(t) || 0) + 1)); return { c, tf, len: toks.length } })
  const N = docs.length, avg = docs.reduce((s, d) => s + d.len, 0) / Math.max(1, N)
  const df = new Map()
  for (const t of q.keys()) df.set(t, docs.reduce((n, d) => n + (d.tf.has(t) ? 1 : 0), 0))
  const k1 = 1.2, b = 0.75
  const scored = []
  for (const d of docs) {
    let s = 0
    for (const [t, qw] of q) {
      const f = d.tf.get(t); if (!f) continue
      const n = df.get(t), idf = Math.log(1 + (N - n + 0.5) / (n + 0.5))
      s += qw * idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * d.len / Math.max(1, avg)))
    }
    if (s > 0) scored.push({ c: d.c, score: s })
  }
  scored.sort((a, b2) => b2.score - a.score)
  const seen = new Set(), out = []
  for (const x of scored) { const k = normText(x.c.text); if (seen.has(k)) continue; seen.add(k); out.push(x) }
  return out
}

export function retrieve(question, comments, k = 12) {
  return rank(question, comments).slice(0, k).map(x => x.c)
}

const clip = (s, n = 700) => { s = String(s || '').replace(/\s+\n/g, '\n').trim(); return s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s }

/* ---------- citation + output hygiene (shared with server/assistant.mjs) ---------- */
const VENDOR = /\b(granite|ollama|ibm|claude|anthropic|bob|qwen|llama|watsonx)\b/gi

/* Keeps only [[ID]] markers whose ID is in validIds, and [[metric:X]] / [[file:path#key]] markers whose ref is in
   validRefs; upgrades bare [ID] when ID is valid; splits combined markers ([[A, B]] -> [[A]][[B]]).
   Scrubs model/vendor names from the prose (never from inside a marker). Returns {text, cited, refs}. */
export function sanitize(text, validIds, validRefs = []) {
  const valid = validIds instanceof Set ? validIds : new Set(validIds || [])
  const vrefs = validRefs instanceof Set ? validRefs : new Set(validRefs || [])
  const cited = [], refs = []
  const keep = tok => {
    if (/^(metric|file):/i.test(tok)) { const r = tok.replace(/^(metric|file):/i, (_, k) => k.toLowerCase() + ':'); if (!vrefs.has(r)) return ''; if (!refs.includes(r)) refs.push(r); return `[[${r}]]` }
    if (!valid.has(tok)) return ''; if (!cited.includes(tok)) cited.push(tok); return `[[${tok}]]`
  }
  let t = String(text || '')
  t = t.replace(/\[\[([^\]]*)\]\]/g, (_, inner) => inner.split(/[\s,;]+/).filter(Boolean).map(keep).join(''))
  t = t.replace(/\[([A-Za-z0-9_-]{4,})\](?!\])/g, (m, id) => (valid.has(id) ? keep(id) : m))
  t = t.split(/(\[\[[^\]]*\]\])/).map(seg => (seg.startsWith('[[') ? seg : seg.replace(VENDOR, 'the assistant'))).join('')
  t = t.replace(/[ \t]+([.,;:!?])/g, '$1').replace(/[ \t]{2,}/g, ' ').replace(/\(\s*\)/g, '').trim()
  return { text: t, cited, refs }
}

/* ---------- deterministic numbers ---------- */
const COUNT_Q = /\b(how many|how much|number of|count|share|percent|percentage|proportion|what fraction|total)\b|%/i
export const isCountQuestion = q => COUNT_Q.test(String(q || ''))

const human = k => String(k).replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').toLowerCase()
function flatten(o, pre = '') {
  const out = []
  for (const [k, v] of Object.entries(o || {})) {
    const key = pre ? `${pre} ${human(k)}` : human(k)
    if (v && typeof v === 'object' && !Array.isArray(v)) out.push(...flatten(v, key))
    else if (typeof v === 'number' && Number.isFinite(v)) out.push([key, v])
    else if (typeof v === 'string' && v.length < 60) out.push([key, v])
  }
  return out
}
const fmtN = v => typeof v === 'number' ? (Number.isInteger(v) ? v.toLocaleString('en-US') : (+v.toFixed(2)).toLocaleString('en-US')) : v

function numbersAnswer(question, scopeLabel, numbers) {
  if (!numbers || typeof numbers !== 'object') return null
  const q = String(question || '').toLowerCase()
  const want311 = /\b311\b|report|request|problem|complaint|service call/.test(q)
  const wantVoice = /comment|letter|email|voice|resident|wrote|writ|said/.test(q) || !want311
  const fams = []
  if (wantVoice && numbers.voice) fams.push(['Letters and emails (public comments)', numbers.voice])
  if (want311 && numbers.requests_311) fams.push(['311 problem reports', numbers.requests_311])
  if (!fams.length) return null
  const parts = fams.map(([label, o]) => {
    const rows = flatten(o)
    return rows.length ? `${label} in ${scopeLabel || 'this scope'}: ${rows.map(([k, v]) => `${k} ${fmtN(v)}`).join('; ')}.` : ''
  }).filter(Boolean)
  if (!parts.length) return null
  return parts.join(' ') + (fams.length > 1 ? ' These are two separate counts and are not added together.' : '')
}

/* ---------- local keyword-search answer ---------- */
const plural = (n, a, b) => `${n} ${n === 1 ? a : b}`
const quoteQ = q => { const s = String(q || '').trim().replace(/[?.!]+$/, ''); return s.length > 60 ? s.slice(0, 57) + '…' : s }

export function searchAnswer({ question, scopeLabel, sectionTitle, comments, numbers }) {
  const scope = scopeLabel || 'this scope'
  const sec = sectionTitle && !/^all sections$/i.test(sectionTitle) ? ` (${sectionTitle})` : ''
  if (isCountQuestion(question)) {
    const t = numbersAnswer(question, scope, numbers)
    if (t) return { text: t, cited: [], engine: 'search' }
  }
  const ranked = rank(question, comments || [])
  if (!ranked.length) return { text: '', cited: [], engine: 'search', note: `No comments in ${scope}${sec} mention “${quoteQ(question)}”.` }
  const top = ranked[0].score
  const matches = ranked.filter(x => x.score >= top * 0.25).map(x => x.c)
  const n = matches.length
  const secs = {}; matches.forEach(c => { const k = c.section || 'Uncategorized'; secs[k] = (secs[k] || 0) + 1 })
  const topSecs = Object.entries(secs).sort((a, b) => b[1] - a[1]).slice(0, 2)
  const st = { support: 0, oppose: 0, other: 0 }; matches.forEach(c => { if (c.stance === 'support') st.support++; else if (c.stance === 'oppose') st.oppose++; else st.other++ })
  const sim = matches.filter(c => c.mock).length
  const cites = matches.slice(0, 3).map(c => c.id)
  let s = `${plural(n, 'comment', 'comments')} in ${scope}${sec} match “${quoteQ(question)}”.`
  if (topSecs.length) s += ` Most are filed under ${topSecs.map(([k, v]) => `${k} (${v})`).join(' and ')}.`
  const sp = []; if (st.support) sp.push(`${st.support} support`); if (st.oppose) sp.push(`${st.oppose} oppose`); if (st.other) sp.push(`${st.other} neutral or unclear`)
  if (sp.length) s += ` Stance: ${sp.join(', ')}.`
  s += ` Closest matches: ${cites.map(id => `[[${id}]]`).join(' ')}.`
  if (sim) s += ` ${sim === n ? (n === 1 ? 'It is a simulated email' : `All ${n} are simulated emails`) : `${sim} of these ${sim === 1 ? 'is a simulated email' : 'are simulated emails'}`}.`
  const out = sanitize(s, new Set((comments || []).map(c => c.id)))
  return { ...out, engine: 'search', note: 'Keyword search summary — the written answer is unavailable right now.' }
}

const ACTION_TYPES = new Set(['select_section', 'set_scheme', 'zoom_tract', 'open_analytics', 'open_comment', 'filter_stance', 'set_view', 'select_district', 'select_area', 'select_tracts', 'compare_places'])

/* ---------- main entry ----------
   askAssistant({question, scopeLabel, sectionTitle, comments, numbers, history, regionTracts})
   -> Promise<{text, cited, refs, actions, engine:'assistant'|'search', note?, seconds?, cost?}>  (never rejects)
   actions: server-validated UI actions, e.g. {type:'set_scheme', id:'prob'} (see server/assistant.mjs). */
export async function askAssistant({ question, scopeLabel, sectionTitle, sectionKey, comments = [], numbers = {}, history = [], regionTracts = [], timeoutMs = 190000, endpoint = '/api/assistant' } = {}) {
  const hits = retrieve(question, comments, 12)
  const fallback = (note) => { const r = searchAnswer({ question, scopeLabel, sectionTitle, comments, numbers }); if (note && r.text) r.note = note; return { refs: [], actions: [], ...r } }
  const context = hits.map(c => ({ id: c.id, section: c.section || '', subsection: c.subsection || '', stance: c.stance || 'unclear', lang: c.lang || 'en', simulated: !!c.mock, place: c.nbhd || '', tract: c.tract || null, text: clip([c.subject, c.text].filter(Boolean).join(' — ')) }))
  const body = { question, scopeLabel, sectionTitle, sectionKey, numbers, regionTracts: (regionTracts || []).slice(0, 250), history: (history || []).slice(-3).map(h => ({ q: String(h.q || ''), text: String(h.text || '').slice(0, 800) })), context }
  const ctl = typeof AbortController !== 'undefined' ? new AbortController() : null
  const timer = setTimeout(() => ctl?.abort(), timeoutMs)
  try {
    const r = await fetch(endpoint, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body), signal: ctl?.signal })
    if (!r.ok) {
      let note
      if (r.status === 429) note = 'The assistant has reached today’s budget — showing a keyword search summary.'
      return fallback(note)
    }
    const j = await r.json()
    if (!j || typeof j.text !== 'string' || !j.text.trim()) return fallback()
    // in-scope comments only; refs were validated by the server against the app's data files
    const out = sanitize(j.text, new Set(comments.map(c => c.id)), Array.isArray(j.refs) ? j.refs : [])
    if (!out.text) return fallback()
    const actions = (Array.isArray(j.actions) ? j.actions : []).filter(a => a && typeof a.type === 'string' && ACTION_TYPES.has(a.type))
    const res = { text: out.text, cited: out.cited, refs: out.refs, actions, engine: 'assistant' }
    if (typeof j.note === 'string' && j.note) res.note = sanitize(j.note, []).text
    if (typeof j.seconds === 'number') res.seconds = j.seconds
    if (typeof j.cost === 'number') res.cost = j.cost
    return res
  } catch {
    return fallback()
  } finally {
    clearTimeout(timer)
  }
}
