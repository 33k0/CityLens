# CityLens — Devpost submission

> Fill in every `[FILL: …]` before submitting. Everything else is written from what is in the repo and the live app.

---

## Step 1 · Project basics

**Project title:** CityLens

**Team name:** Civics

**Team members:** [FILL: every team member's full name]

**Short summary** (one line for the card):

> CityLens shows San José council staff who they are hearing from, and who they aren't. It maps public comments,
> 311 reports and police calls by census tract and compares them with who actually lives there. An IBM Bob assistant
> answers questions with cited sources and drives the map.

---

## Step 2 · Project description

### What problem are we solving?

San José council offices receive hundreds of letters and emails on contested agenda items. The people who write in
are not a random sample of the city. Nationally and locally, homeowners, higher-income residents and English speakers
are over-represented in public comment, while renters and limited-English households write in far less, even where
problems pile up. Staff can count comments, but they cannot easily see three things:

- **where** the comments come from
- **which neighborhoods are silent** on an issue that affects them
- whether that silence means "no problem" or "not being heard"

### Who experiences this problem?

- **Council staff and council members**, who make decisions on what reaches their inbox.
- **Residents in underheard neighborhoods**, often renters, lower-income and limited-English households in Equity
  Priority Communities. Their needs show up in 311 reports and police calls but rarely in written comment.

### What does CityLens do?

CityLens is a map-first workspace for council staff, built on real San José data.

- **Places every comment in a census tract** (never finer, for privacy). It does this from addresses, intersections,
  neighborhood names or ZIP codes in the text, and labels each comment by section, subsection and stance.
- **Three map views:**
  - **Voice:** comments per 1,000 residents.
  - **Problems:** 311 reports *or* police calls per 1,000 residents.
  - **Underheard:** where problems are reported but few people write in.
  - **Side-by-side** puts Voice and Underheard next to each other.
- **Keeps three families separate.** Comments, 311 reports and police calls are compared only through per-resident
  rates and rankings. They are never added together.
- **"Who we are not hearing from."** A census tract is flagged as underheard only when it sends less than half its
  population share of comments *and* either reports problems at or above the city rate or has many limited-English
  households. Low-comment, low-problem census tracts are labeled "quiet" instead, so staff aren't sent chasing
  neighborhoods that are simply fine. The rule lives in a team settings file, not in AI judgment.
- **Fairness metrics with IBM AI Fairness 360.** Disparate impact and statistical parity difference for low-income,
  majority non-white, renter-majority and high limited-English census tracts.
- **Regions.** Draw one or several regions (overlaps merge), open any council district or named neighborhood, and
  compare two places side by side.
- **Analytics dashboard** for the city, a region or one census tract:
  - a "How much to trust these numbers" card
  - population, renters, language and income against the city
  - what people write about, support vs. opposition on policy sections
  - 311 and police calls over time
  - a sortable "Who we are not hearing from" table that compares each census tract's voice with its problems
- **An IBM Bob staff assistant.** Staff ask plain questions ("Why isn't District 5 writing in?", "Compare downtown
  and Willow Glen"). Bob answers with:
  - the finding and what stands out
  - likely reasons tied to measured correlations or labeled background
  - caveats and a next step
  - a clickable source on every claim

  It also drives the app: it opens districts and neighborhoods, compares two places, switches to side-by-side, or
  opens a section's analytics.

### How does AI contribute?

AI does the reading, sorting and explaining. Code does the counting.

- **IBM Bob built the comment taxonomy from scratch.** It read the corpus and proposed the eight sections and their
  subsections; nothing was preset.
- **IBM Bob labeled every comment.** All 1,299 letters and emails got a section, subsection, stance and an
  **exact evidence quote**. Code rejects any label whose quote is not a verbatim substring
  of the comment. Duplicates and form-letter campaigns are collapsed first so each voice counts once.
- **IBM Bob mapped the city's 311 service types and all 198 police call types** to the same sections, so comments,
  311 and police calls can be compared by topic.
- **IBM Bob is the in-app assistant.** It runs headless with a custom CityLens skill and repo rules. Each question
  carries a data brief computed by the app (city, district and place figures with pre-checked rankings, correlations,
  background notes). The server validates every citation and every UI action against the app's data before showing
  it. Typical answer: about 10 seconds and about $0.08.
- **Fairness and statistics are deterministic:** AIF360, pandas and Spearman correlations. AI never invents a number.

### Technologies, tools, frameworks and datasets

**AI and analysis**
- IBM Bob Shell 2.0.6: taxonomy, labeling, 311 and police call mapping, staff assistant
- IBM AI Fairness 360: disparate impact and statistical parity
- pandas, GeoPandas, Shapely, SciPy: Spearman associations
- RapidFuzz and MinHash (datasketch): duplicate and campaign detection
- pdfplumber and Tesseract OCR: scanned council letters
- langdetect

**App**
- React, TypeScript and Vite
- D3 for the maps and charts; Turf for region merging
- Vercel: static site plus a serverless function that runs IBM Bob

**Real datasets**
- **City Council "Letters from the Public"** (Legistar), 2025–2026: 195 unique real letters, OCR'd and de-identified at ingest
- **San José 311 Service Requests** (Open Data, CC0), July 2025 to October 2026: 217,415 problem reports placed in census tracts, in 22 service types
- **San José Police Calls for Service** (Open Data, CC0), same months: 352,566 calls, 88% placed in census tracts using the city's street address ranges
- **U.S. Census ACS 5-year 2020–2024**: population, renters, income, race, household language (C16002)
- **Census TIGER 2024**: 215 census tracts clipped to city limits
- **MTC Equity Priority Communities 2024**
- **San José GIS:** council districts, neighborhoods, street centerlines

**Simulated data, clearly labeled in the app:** 1,022 simulated constituent emails.
- 158 come from a team-supplied set.
- 864 were generated to fill out every section and the whole city (see Step 5).

### What impact could CityLens create?

[FILL]

### Limitations and next steps

**Known limitations** (all disclosed in the app):
- **Most comments are simulated.** 1,022 of 1,217 unique comments are simulated emails. The real letters cover a
  limited set of agenda items. Patterns in the comment data illustrate the method; they are not findings about
  San José.
- **Location coverage is partial.** 56% of comments include enough location information to be placed in a census tract.
- **311 and police calls measure reporting, not need.** 311 reflects who uses 311. Police calls are calls, not
  crimes: they include officer-initiated stops and follow where officers patrol.
- **Correlations describe places, not people,** and do not show cause.
- **No human has reviewed the labels yet.** AI labels are checked by code (exact evidence quotes), not by staff.
- **The assistant's background notes on San José history** are general context and should be verified before
  public use.

**Next steps:** [FILL]

---

## Step 3 · Demonstration

- **Live app:** https://city-lens-livid.vercel.app
- **Demo video (≤ 3 min):** [FILL: link]

**Suggested 3-minute demo path:**
1. **Map, Voice view:** where comments come from. Switch to **Problems**, then flip the filter to **Police calls**.
2. **Underheard + Side-by-side:** high problems, low voice.
3. **City analytics:** the trust card, then "Who we are not hearing from" (red = problems but no voice; purple = limited English).
4. **Ask Bob:** "Tell me what the community with the most voice and least voice is and why." It answers with sources,
   outlines District 8 vs District 4 side by side, and a source chip opens the data behind a claim.
5. **Draw two regions:** they combine into one analysis.

---

## Step 4 · Technical work

- **Repository:** https://github.com/33k0/CityLens
- **README:** setup is in `README.md` (`npm install`, Python venv, `npm run demo`, `npm test`, `npm run build`).
- **Live chat on the deploy** needs `BOB_API_KEY` and `BOB_LICENSE_ACCEPTED=true` set as environment variables in
  Vercel. No keys are in the repo; `.env.local` is gitignored.
- **Docs and code worth pointing judges to:**
  - `DECISIONS.md`: design decisions and why
  - `docs/METRICS.md`: every metric with its formula
  - `.bob/skills/app-analyst/SKILL.md`: the assistant's skill
  - `.bob/rules/civic-data.md`: the civic data rules Bob follows
  - `scripts/`: the full data pipeline (`npm run data`)

---

## Step 5 · Use of AI (disclosure)

**IBM Bob (in the product and the data pipeline)**
- Derived the comment taxonomy from the corpus.
- Labeled all 1,299 comments: section, subsection, stance, exact evidence quote, and whether each asks for a specific fix.
- Mapped 311 service types and all 198 police call types to sections.
- Powers the staff assistant: a custom skill plus repository rules, with server-side validation of every citation
  and UI action.
- **Why it fit:** Bob works directly inside the repository as an agent. It reads the real data files, follows
  project rules (`.bob/rules/civic-data.md`: tract-level only, never sum comments and 311, label simulated data), and
  its skills made the labeling and the assistant repeatable and auditable.

**IBM AI Fairness 360** computes the fairness metrics; we cross-check them against pandas.

**Anthropic Claude (development assistant)**
- Claude Code was used to write and debug much of the code, data pipeline and UI.
- Claude subagents generated the 864 additional simulated emails from fixed templates. The topic mix follows San
  José's own 311 data, and the emails name no real people or places in their text.
- The team reviewed, tested and is responsible for all of it: 50 front-end and 138 Python tests.

**What AI does not do in CityLens:** it never computes the counts, rates, rankings or fairness metrics, and it never
sets the underheard rule. Those are deterministic code and team settings.

---

## Step 6 · Final checklist

- [ ] Every team member listed on Devpost
- [ ] `[FILL]` sections completed (impact, next steps, video)
- [ ] Vercel env vars set and redeployed; live chat answers a question on https://city-lens-livid.vercel.app
- [ ] Live link and repo link open in a private/incognito window
- [ ] README updated (its "Status" section still describes an early milestone)
- [ ] No keys in the repo or the video
