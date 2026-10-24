/* Guided tour: a spotlight over the real UI plus a step card. Each step can set app state (the "simulation") before it
   is shown, so the tour clicks through the app for the viewer. It never sends a chat message (no IBM Bob spend). */
const SEEN = 'citylens.tour.v1'
const qs = s => document.querySelector(s)
const cardWith = text => [...document.querySelectorAll('section.card')].find(c => c.querySelector('h4')?.textContent.includes(text))

export function tourSeen() { try { return localStorage.getItem(SEEN) === '1' } catch { return true } }

export function startTour({ S, D, ITEM, render, maps }) {
  if (document.querySelector('.tour')) return
  const city = () => { S.region = { name: 'All of San José', poly: 'city' }; S.regions = [S.region] }
  const home = () => { S.view = 'main'; S.sbs = false; S.armed = false; S.compare = false; S.menu = null; S.inspector = null; S.srcView = null; S.selTract = null; S.tractDetail = null; S.modal = false; city() }
  const gapTract = () => [...D.tracts].filter(t => t.pop > 2500 && t.gap != null).sort((a, b) => a.gap - b.gap || b.pop - a.pop)[0]
  const EX = 'Which neighborhoods report the most problems but send the fewest comments, and why?'

  const steps = [
    { title: 'Welcome to CityLens', text: 'CityLens shows council staff <b>who they are hearing from, and who they are not</b>. This tour clicks through the app for you. It takes about a minute.', run: home },
    { el: '.top .picker', also: '.top .menu', title: 'Pick a section', text: 'Every comment is labeled into a section, like housing or transportation. Pick one from this list and the whole app updates. <b>All sections</b> shows everything.', run: () => { home(); S.menu = 'item' } },
    { el: '#m0', title: 'Voice map', text: 'Each shape is a census tract. <b>Darker red = more public comments per 1,000 residents.</b> Hatched means no comments yet.', run: () => { home(); S.scheme = 'voice' } },
    { el: '#m0', title: 'Problems map', text: 'The same census tracts, colored by <b>311 reports per 1,000 residents a year</b>. You can switch this to police calls in the filters.', skip: () => !ITEM.n311, run: () => { home(); S.scheme = 'prob' } },
    { el: '#m0', title: 'Underheard map', text: '<b>Purple = many problems, few comments.</b> The darkest census tracts are where problems outpace voice the most. These are the places worth reaching out to.', run: () => { home(); S.scheme = 'gap' } },
    { el: '.rmodal', title: 'Click a census tract', text: 'Clicking a census tract opens its card: who lives there, how much it writes in, and what it reports. <b>Double-click</b> to zoom in.', run: () => { home(); const t = gapTract(); if (t) { S.selTract = t.id; S.tractDetail = t.id; S.modal = true; S.right = true } } },
    { el: '.mapdraw', title: 'Draw your own region', keepZoom: true, text: 'Use <b>Draw region</b> on the map to outline any area. You can draw several, and overlapping drawings merge. On the map is an example drawn area on the East Side, with its combined card on the left.', run: () => { home(); const r = S.saved[0]; S.region = r; S.regions = [r]; S.modal = true } },
    { el: '.rail', title: 'Filters', text: 'Narrow the map by <b>section and subsection</b>, by stance (support or oppose, for policy sections) and by <b>311 report or police call type</b>.', run: home, after: () => { const sc = qs('.rail .scroll'); if (sc) sc.scrollTop = 0 } },
    { el: 'section.heard', title: 'Who gets heard', text: 'IBM AI Fairness 360 results in plain language. <b>Purple bars</b> are under-represented groups, <b>grey</b> is everyone else. Renter and limited-English neighborhoods are heard about half as often.', run: home },
    { el: '.maps', title: 'Side-by-side', text: 'Compare two map types or two places at once. The link button lets both maps zoom together or separately.', run: () => { home(); S.sbs = true; S.drawer = false } },
    { el: () => cardWith('How much to trust'), title: 'Analytics', text: 'Open analytics for the city, a region or one census tract. Start with <b>How much to trust these numbers</b>: how many comments were placed on the map, how many are real, and how sure the labels are.', run: () => { home(); S.view = 'analytics' } },
    { el: () => cardWith('Who we are not hearing from'), until: '.mvtab tbody tr:nth-child(4)', title: 'Who we are not hearing from', text: 'The underheard census tracts, sortable by any column. The color runs from <b>red (almost no voice for its problems)</b> to yellow (city level).', run: () => { home(); S.view = 'analytics' } },
    { el: '.rpanel', title: 'Ask IBM Bob', text: 'Ask questions in plain English. Every claim comes with a <b>clickable source</b>, and Bob can move the map for you. We typed an example below. Press <b>Enter</b> to ask it, or write your own.', run: home, after: () => { const ta = qs('.cbox textarea'); if (ta) ta.value = EX } },
    { el: '.top [data-act="tour"]', title: 'You are all set', text: 'Replay this tour any time from the <b>Tour</b> button.' },
  ]

  const root = document.createElement('div'); root.className = 'tour'
  root.innerHTML = '<div class="tourblock"></div><div class="tourhl"></div><div class="tourcard" role="dialog" aria-live="polite"></div>'
  document.body.appendChild(root)
  const hl = root.querySelector('.tourhl'), card = root.querySelector('.tourcard')
  const live = steps.filter(s => !s.skip || !s.skip())
  let i = 0, tid = 0

  function place() {
    const s = live[i]; const t = typeof s.el === 'function' ? s.el() : s.el ? qs(s.el) : null
    const W = innerWidth, Hh = innerHeight, cw = Math.min(360, W - 32)
    card.style.width = cw + 'px'
    root.classList.toggle('nohl', !t)
    if (!t) { hl.style.cssText = `left:${W / 2}px;top:${Hh / 2}px;width:0;height:0`; card.style.left = (W - cw) / 2 + 'px'; card.style.top = Math.max(16, Hh / 2 - card.offsetHeight / 2) + 'px'; return }
    let r = t.getBoundingClientRect(), p = 6
    const t2 = s.also && qs(s.also)
    if (t2) { const r2 = t2.getBoundingClientRect(); r = { left: Math.min(r.left, r2.left), top: Math.min(r.top, r2.top), right: Math.max(r.right, r2.right), bottom: Math.max(r.bottom, r2.bottom) } }
    const t3 = s.until && qs(s.until) /* stop the spotlight here: the header and first rows are enough */
    if (t3) r = { left: r.left, top: r.top, right: r.right, bottom: Math.min(r.bottom, t3.getBoundingClientRect().bottom) }
    const x = Math.max(4, r.left - p), y = Math.max(4, r.top - p), w = Math.min(W - 8, r.right + p) - x, h = Math.min(Hh - 8, r.bottom + p) - y
    hl.style.cssText = `left:${x}px;top:${y}px;width:${w}px;height:${h}px`
    const ch = card.offsetHeight, g = 14
    let cx, cy
    if (x + w + g + cw < W) { cx = x + w + g; cy = y }                 /* right */
    else if (x - g - cw > 0) { cx = x - g - cw; cy = y }               /* left */
    else if (y + h + g + ch < Hh) { cx = x; cy = y + h + g }           /* below */
    else { cx = x + w - cw - 16; cy = y + h - ch - 16 }                /* inside, bottom-right of a big target */
    card.style.left = Math.max(16, Math.min(W - cw - 16, cx)) + 'px'
    card.style.top = Math.max(16, Math.min(Hh - ch - 16, cy)) + 'px'
  }

  function show() {
    const s = live[i]
    if (s.run) { s.run(); render(); if (!s.keepZoom) maps().forEach(m => m.reset()) }
    if (s.after) s.after()
    const last = i === live.length - 1
    card.innerHTML = `<div class="tc-top"><span class="tc-n">${i + 1} of ${live.length}</span><button class="tc-x" data-t="end" aria-label="Close tour">×</button></div>
      <h3>${s.title}</h3><p>${s.text}</p>
      <div class="tc-bot"><div class="tc-dots">${live.map((_, k) => `<i class="${k === i ? 'on' : k < i ? 'done' : ''}"></i>`).join('')}</div>
      ${i ? '<button class="btn" data-t="back">Back</button>' : '<button class="btn tc-skip" data-t="end">Skip</button>'}
      <button class="btn pri" data-t="${last ? 'end' : 'next'}">${last ? 'Done' : i ? 'Next' : 'Start the tour'}</button></div>`
    const t = typeof s.el === 'function' ? s.el() : s.el ? qs(s.el) : null
    if (t) { /* bring it into view inside its own scroll panel; the stage itself must never scroll */
      let sc = t.parentElement; while (sc && sc !== document.body && !/(auto|scroll)/.test(getComputedStyle(sc).overflowY)) sc = sc.parentElement
      if (sc && sc !== document.body) { const a = sc.getBoundingClientRect(), b = t.getBoundingClientRect(); if (b.top < a.top || b.bottom > a.bottom) sc.scrollTop += (b.top - a.top - 24) * sc.clientHeight / a.height } /* the stage is CSS-scaled */ }
    place(); clearTimeout(tid); tid = setTimeout(place, 120) /* maps fit after render */
    card.querySelector('.btn.pri').focus({ preventScroll: true })
  }

  function end() {
    try { localStorage.setItem(SEEN, '1') } catch { /* private window: the tour just shows again next time */ }
    const keep = i === live.length - 1
    root.remove(); removeEventListener('keydown', key, true); removeEventListener('resize', place)
    if (!keep) { home(); S.scheme = 'voice'; render() }
  }
  const go = d => { i = Math.max(0, Math.min(live.length - 1, i + d)); show() }
  function key(e) {
    if (e.key === 'Escape') { e.stopPropagation(); end() }
    else if (e.key === 'ArrowRight') { e.preventDefault(); if (i === live.length - 1) end(); else go(1) }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); go(-1) }
  }
  root.addEventListener('click', e => { const b = e.target.closest('[data-t]'); if (!b) return; const t = b.dataset.t; if (t === 'next') go(1); else if (t === 'back') go(-1); else end() })
  addEventListener('keydown', key, true); addEventListener('resize', place)
  show()
}
