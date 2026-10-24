# DECISIONS.md — every assumption, with evidence

Dates are absolute. Newest at the bottom of each section.

## Inputs that were missing (2026-10-23)

- **`ONESHOT_ADDENDUM.md` and the four `.bob/` files were not supplied.** The opening prompt says to paste them after the
  main document; the working directory was empty. Everything so far follows the main document alone. Where the main
  document defers to the addendum (Bob skills, pipeline step order a→h, assistant bridge, AIF360 export design, lasso rules,
  acceptance checklist) a placeholder is noted and will be filled from the addendum when it is provided, or written to the
  main document's description of it otherwise. `.bob/README.md` records this.
- **`scripts/fairness.py`, `web/fairness.js`, `web/fairness.test.mjs` were absent** (correction 1 of the prompt). They will
  be written to spec in Milestone 6.
- **`bob` CLI and `ollama` are not installed on this machine** (`which bob ollama` → not found, 2026-10-23). Milestone 5
  will run the test call first per correction 2; if still absent, every Bob/LLM step runs its fallback and
  `provenance.json` will show `engine: "fallback"`.

## Milestone 0 — scaffold

- Vite 8 + React 19 + TypeScript (`npm create vite@latest -- --template react-ts`), Tailwind v4 via `@tailwindcss/vite`.
- Python 3.11 venv at `.venv` (system default is 3.14, which aif360's pins do not support). `aif360` installed first and
  alone, then pandas, geopandas, shapely, pyproj, httpx, beautifulsoup4, lxml, rapidfuzz, datasketch, langdetect,
  python-dotenv, pillow, pytest. `opencv-python-headless` deferred to Milestone 2.
- `npm run data` → `scripts/data.sh`, which runs pipeline steps a→h in order and skips scripts that do not exist yet,
  so the command works at every milestone. `npm run demo` = offline data + dev server; `npm run demo:warm` re-scrapes.
- `npm test` runs vitest (browser-side tests, none yet) then pytest.

## Milestone 1 — written comments from Legistar "Letters from the Public" (replaces Granicus, 2026-10-23)

### Why the source changed
- Granicus eComments on `sanjose.granicusideas.com` have been nearly unused since 2023 (the 2026-10-27 council meeting
  has 2 comments). Current written public comment is emailed to the Clerk and attached to each agenda item on Legistar
  as a PDF named "Letters from the Public". The Granicus scraper, its test, fixture and raw cache were removed.

### Which path worked
- **Legistar Web API, enabled for `sanjose`.** Test call `GET https://webapi.legistar.com/v1/sanjose/Events?$top=1`
  → HTTP 200 (2026-10-23). Used: `Events?$filter=EventDate ge datetime'2025-01-01' and EventBodyName eq 'City Council'`,
  `Events/{EventId}/EventItems?AgendaNote=1&MinutesNote=1&Attachments=1` (attachments come inline, so
  `Matters/{id}/Attachments` was only used as a cross-check on matter 16374 / 26-1082). The HTML fallback
  (Calendar.aspx → MeetingDetail.aspx → LegislationDetail.aspx) is implemented in `inventory_html()` but was never
  exercised; its selectors are untested.
- Attachment URLs are `https://legistar.granicus.com/sanjose/attachments/<guid>.pdf`, not `View.ashx`; both are served
  by the same host and the script just follows whatever hyperlink the API returns.

### Inventory (2026-10-23)
- 102 City Council events 2025-01-01 → 2026-10-23; **405 attachments matching /letters? from the public/i on 300
  matters across 82 meetings** (229 in 2026, 176 in 2025). Name variants: "Letter from the Public" 139,
  "Letters from the Public" 124, "… - N of M" splits for the rest. "Letters Received Post Meeting" attachments exist
  and are deliberately excluded by the regex. 115 attachments sit on matters whose title matches the
  land-use / housing / transportation keyword list (`priority=true`).
- **Download was stopped by the user after 15 attachments** (the full set is several GB at 1 req/s; the first files
  took ~3 s each and then a 9 MB file stalled). `data/legistar_items.json` and its fixture were trimmed to the 15 PDFs
  on disk. Re-running `scripts/ingest_legistar.py` resumes (it caches by attachment id) if the full set is wanted.

| matter | meeting | title | pages | OCR pages | letters |
|---|---|---|---|---|---|
| 25-011 | 2025-01-14 | 2025 Legislative Program and Legislative Priorities | 13 | 13 | 9 |
| 25-012 | 2025-01-14 | Fall Intergovernmental Relations Report | 2 | 1 | 1 |
| 25-018 | 2025-01-14 | Options for Expanding Alternative Response and Co-Response Programs (2 PDFs) | 26 | 4 | 6 |
| 25-008 | 2025-01-14 | Grant Agreement, Supportive Parking for RVs (priority) | 1 | 1 | 1 |
| 25-025 | 2025-01-14 | Boards and Commissions Appointments | 1 | 1 | 1 |
| 25-065 | 2025-01-21 | Code Enforcement Operations Study Session | 6 | 4 | 2 |
| 25-054 | 2025-01-28 | Exception to the Multifamily Housing Revenue Bond policy (priority) | 3 | 3 | 2 |
| 25-059 | 2025-01-28 | Interim Appointment to Council District 3 | 94 | 71 | 25 |
| 25-081 | 2025-02-04 | Resolution Reaffirming Commitment to Safety of Immigrant Communities (4 PDFs) | 379 | 311 | 177 |
| 25-085 | 2025-02-04 | Options for Expanding Alternative Response and Co-Response Programs (2 PDFs) | 26 | 4 | 6 |
| **total** | | **10 matters, 15 PDFs** | **551** | **413** | **230** |

### Parsing (`scripts/ingest_letters.py`, replaces the first `parse_letters.py`)

- **Local PDFs only, no crawling tonight.** Input is `data/raw/legistar/<matter_file>/*.pdf` plus a hand-filled sidecar
  `data/raw/legistar/items.csv` (`matter_file, title, meeting_date, body, legistar_url, agenda_number,
  comment_deadline`); the same PII-free table is committed as `data/legistar_items.csv`. All of a matter's PDFs are
  processed together. `--crawl` is a stub that exits 2; `scripts/ingest_legistar.py` (Web API inventory + download)
  stays in the repo but is not in `npm run data`.
- **Text:** pdfplumber; pages under 50 characters are OCR'd with tesseract 5 through pypdfium2 at 2× and tagged
  `ocr=true`. Early-2025 bundles are mostly scans: 251 of 271 letters needed OCR. Page text is cached in
  `data/raw/legistar/textcache/` (gitignored), so re-parses take under a second.
- **New-email detection:** an email starts on a page whose first 3 non-empty lines contain the Outlook logo line
  (OCR variants such as "Ga Outlook" included); web-print continuation pages are not new emails. Without a wrapper,
  an email starts at a top-of-page `From:` block or a `From:`+`Sent:` block. Memo-style header blocks inside a
  letter do not split it. City forwarding layers (Agendadesk, City Clerk, Rules Committee, Mayor's office, district
  inboxes, staff notes with no text) are skipped and never treated as the sender.
- **Letter vs exhibit:** a unit is a letter if an inner `From:`+`Subject:` or `From:`+`Sent:` block appears within
  its first 40 non-empty lines, extended for OCR damage ("rom:", a lost `From:` leaving `Sent:`+`Subject:`) and
  direct sends whose Outlook header names a non-City sender. Otherwise it is an exhibit attached to the preceding
  letter in the same PDF. The body ends at the City "outside the City email system" footer, before an
  EXHIBIT/ATTACHMENT page, or at the sign-off page when attachments are listed. Later pages are exhibit pages,
  counted in `pages_exhibit` and excluded from comment counts. Leading orphan pages go to `pages_unattributed`.
  When a body is under 200 characters and has exhibits ("see attached"), the first 2 exhibit pages are appended to
  the text so the letter keeps its substance.
- **`commenter_type`** in priority order developer_or_counsel → government → organization → resident, from the
  signature block, the sender line, and the first exhibit page's letterhead. "City of San José" and `sanjoseca.gov`
  never count as government cues because they are the recipient. Bulk-advocacy domains (actionnetwork.org,
  everyaction.com) are not organization cues. The literal rules give some debatable labels: a consultant's LLC
  signature becomes developer_or_counsel and a school-district trustee becomes government.
  Result: 235 resident, 33 organization, 2 government, 1 developer_or_counsel.
- **Per-item pages of record:** `letters_by_type`, `pages_by_type`, and `pages_summary`, e.g. "81% of pages from 47
  residents; 8 organization letters; 1 developer/counsel letter; 1 government agency letter". Shown on the item
  header; the Region Summary will use it too.
- **`after_deadline`:** inner `Sent:` (Pacific, via zoneinfo) vs `comment_deadline`; date-only deadlines mean end of
  day. All 271 are `null` today because no deadlines have been entered in `items.csv` yet.
- **Location:** signature-block street addresses and cross-streets go only to the gitignored
  `data/raw/legistar/location_hints.json`. OCR'd street and neighborhood names are fuzzy-corrected there (rapidfuzz
  ratio ≥ 85 against NEIGHBORHOODS plus 55 major streets, same word count and first letter, street suffix attached:
  "Helger Way" → "Holger Way" scores 90). 8 letters carry an address hint; none needed correction.
- **PII:** sender name and email from the inner `From:` → `identity_hash`, then dropped. Emails and phone numbers in
  bodies become `[email removed]` / `[phone removed]`. Person-name lines within 4 lines after a sign-off and
  sender-name tokens in the signature tail are dropped. **Known gap:** OCR mangles some names, so a few signature
  names survive (one example in a 25-059 letter). These letters are already public record on Legistar with names,
  but the scrubber is not yet complete.
- `comment_id = "L" + sha1(matter_file + body)[:8]`; 73 exact-text repeats get `-2`, `-3` suffixes and
  `duplicate_of`. Stance is `unclear` / `pending_llm` until Milestone 5.
- **Per-item results (15 PDFs, 271 letters):**

  | matter | letters | exhibit pages | pages of record |
  |---|---|---|---|
  | 25-008 | 1 | 0 | 100% of pages from 1 resident |
  | 25-011 | 10 | 0 | 77% from 9 residents; 1 organization letter |
  | 25-012 | 1 | 1 | 100% from 1 organization |
  | 25-018 (2 PDFs) | 4 | 17 | 100% from 4 organizations |
  | 25-025 | 1 | 0 | 100% from 1 resident |
  | 25-054 | 2 | 0 | 100% from 2 organizations |
  | 25-059 | 57 | 28 | 81% from 47 residents; 8 organization; 1 developer/counsel; 1 government |
  | 25-065 | 3 | 0 | 50% from 2 residents; 1 organization letter |
  | 25-081 (4 PDFs) | 188 | 17 | 91% from 169 residents; 12 organization; 1 government |
  | 25-085 (2 PDFs) | 4 | 17 | 100% from 4 organizations |

  The 25-018 and 25-085 bundles contain the same October 2024 committee letters, so those letters appear under both
  matters. 10 letters have no readable sent time.

## Plan revision (2026-10-23, evening): 311 (real) + Legistar letters (real, local PDFs) + two simulated channels

- Data sources are now: San José 311 Service Request Data (real, CC0), Letters from the Public PDFs already on disk
  (real, 10 matters / 15 PDFs, no crawling tonight), simulated emails (Milestone 2), simulated on-site submissions and
  a live `/submit` form (Milestone 2/7). Mock "Letters from the Public" are never generated.
- Per the user: **311 rows are limited to 2026 plus the second half of 2025** (`--since 2025-07-01` default).

## Milestone 3 — tracts, ACS, districts, neighborhoods (`scripts/build_tracts.py`)

- **City boundary:** San José GIS ArcGIS REST `PLN/PLN_AdministrativeBoundaries/MapServer/7` ("Incorporated"), GeoJSON
  in WGS84, 468.1 km². The Census Place fallback is implemented but was not needed.
- **Tracts:** TIGER `cb_2024_06_tract_500k` (2020 tract geography), 408 tracts in Santa Clara County; kept those with
  ≥30% area overlap with the city or a centroid inside it → **215 tracts** (203 also have their centroid inside the
  city). Geometry clipped to the city, simplified at 0.0003°, coordinates rounded to 6 decimals; areas computed in
  EPSG:3310. `aland` is TIGER's whole-tract land area, not the clipped area.
- **ACS:** 5-year **2024** (2020–2024). The Census Data API now rejects keyless requests, so the script streams the
  table-based summary files (`acsdt5y2024-<table>.dat`) and caches only the county rows (~600 KB); with
  `CENSUS_API_KEY` set it uses the API instead. `pct_renter` = B25003_003/B25003_001; `pct_nonwhite` =
  1 − B03002_003/B03002_001 (Hispanic white counts as nonwhite); `pct_lep` = (C16002_004+007+010+013)/C16002_001, i.e.
  limited-English *households*. Negative sentinels/zero denominators → empty (none in the 215 tracts). 14 tracts sit at
  the $250,000+ income top code. Population sum 1,005,133, slightly above the city's population because edge tracts
  keep whole-tract population while shapes are clipped.
- **Council districts:** `PLN/PLN_AdministrativeBoundaries/MapServer/1`, `district` from `DISTRICTINT`, all 10 fetched.
- **Neighborhoods:** `data/neighborhoods.csv` has 315 rows: 60 curated names (38 centroids from the city
  `OPN_OpenDataService/MapServer/549` Neighborhoods layer, 22 hand-entered for broad areas/corridors) plus 255 further
  city polygon names (`source=sjgis`, no aliases; some are generic like "Commercial", "Union" and may need dropping
  before fuzzy matching). `tract_ids` = containing tract first, then tracts with centroids within 1.2 km. Rancho
  Rinconada and Lynbrook are mostly Cupertino/Saratoga but kept because residents use the names.
- **Block groups:** ACS 2024 B01003 for 1,173 county block groups (611 inside San José tracts), `share_of_tract`.
- Raw downloads cached in `data/raw/census/` (gitignored); 1 req/s; 5 retries with backoff; `--offline` skips when
  outputs exist.

## 311 Service Requests (`scripts/ingest_311.py`)

- **Columns (no published schema; inspected 2026-10-23 via CKAN `datastore_search`):** `Incident_ID, Status, Source,
  Category, Service Type, Latitude, Longitude, Date Created, Date Last Updated, Department`. No address, zip, or
  council-district column exists, so the "address" and "zip" geocoding tiers never apply to 311; location is
  point-in-polygon on our 215 tracts and the coordinates are then discarded (`data/raw/311/` keeps the originals).
- `Service Type` (19–20 values) is the clean taxonomy field; `Category` is 60–70% null and free-text, kept as
  `subcategory_raw`. Provisional mapping into our categories is `CATEGORY_MAP` in the script (re-keyed to
  `data/categories.json` in Milestone 5): junk/dumping/container/missed collection/sweeping → sanitation_dumping;
  graffiti → graffiti_blight; vehicle concerns → abandoned_vehicles_parking; streetlight/pothole/sidewalk/water →
  streets_infrastructure; encampment → homelessness_encampments; fireworks → noise_nuisance; "Other Issues", "RGR?CCC"
  → other.
- Files: 2025 CSV 341,441 rows (44 MB), 2026 CSV 280,718 rows (35 MB, through 2026-10-22). Window 2025-07-01 → today:
  **455,545 rows**. Last 30 days ≈ 28,000; September 2026 28,170.
- **49.5% of rows (225,452) carry literal (0, 0) coordinates** and are concentrated in account-based request types
  (Junk pickup 119,873; Other Issues 53,420; Container Issues 27,192; Water 7,557; Missed Collection 7,094). A few dozen
  more are clearly wrong (Southern California, India). These get `location_precision="none"` and stay in totals but
  not in any tract count. **224,694 rows (49.3%) are located to a San José tract**, all 215 tracts receive some.
  Located rows by category: other 61,219; graffiti 51,070; abandoned vehicles 50,442; sanitation 41,280; streets
  11,240; encampments 7,826; noise 1,617.
- Exports: `public/data/requests_311_by_tract.json` (tract × category × month counts, 266 KB) and a random 200-row
  anonymized sample for the inspector. `data/requests_311.csv` (455k rows) is gitignored. The 311 join is step a3 in
  `scripts/data.sh`, placed after `build_tracts.py` because it needs the tract polygons.
- **311 update (user, 2026-10-23 evening):** aggregation only, no LLM on 311 rows. "Request type" in the source is
  `Service Type` and has only **20 distinct values** (not 40–60); `Category` (70 distinct, 64% null) refines it. The
  hand-filled mapping is `data/taxonomy_311.csv` with two-level keys: a specific `(Service Type, Category)` row wins
  over the `(Service Type, *)` row. 10,795 rows with a blank Service Type map to `other` (logged on every run).
  Water, "RGR?CCC" (garbage/recycling customer contacts) and billing subtypes map to `utilities_billing` so they do
  not pollute the problems layer. Exports now carry `months_covered`, per-tract totals, ACS population, and
  `rate_per_1k_annualized` = total ÷ population × 1000 × 12/months_covered (median 157 per 1k per year, range
  13–710); the 311 panel has a client-side month-range slider and the sample is a seeded 500 rows with month only.
  Output is 345 KB (target < 500 KB). The window stays 2025-07-01 onward per the earlier instruction (2026 + second
  half of 2025), which is 16 months rather than 12.

## Channel separation rule (user, 2026-10-23)

- Two families, kept apart everywhere. **Voice** = letters + email + site submissions. **Problems** = 311.
  No panel, metric, ranking, share chart or map layer ever adds a 311 count to a voice count.
- Cross-family comparison uses citywide percentiles of per-1k-resident rates, never raw counts side by side.
  "Problems without voice" = `problem_pct ≥ 70` and `voice_pct ≤ 30`, both percentiles shown on the row.
- Fairness (DI/SPD) is computed per family with the same protected attributes; the card shows two labeled rows.
- Theme ranking under the three weighting schemes is voice-only; 311 gets a category-by-volume table.
- Region Summary has two stacked sections ("What residents said" and "What residents reported to 311"), and
  "Who we're not hearing from" uses voice only. The assistant's numbers object has separate `voice` and
  `requests_311` keys and its answers name the family.
- Implemented so far: the viewer labels each panel by family, "All items" is voice-only, 311 is its own entry with
  its own month slider, and every share or rank on the 311 panel is within 311 only.
- Shared logic lives in `src/data/families.ts` with a Python mirror in `scripts/families.py`:
  `sumWithinFamily` / `sum_within_family` throw if a count from the other family is added, shares are computed
  within one family, rates are annualized per 1,000 residents, and percentiles use mid-rank ties
  (`100 × (below + 0.5 × equal) / n`, tracts without population excluded). `tests/fixtures/families_parity.json` is
  checked by both vitest and pytest so the two implementations cannot drift. Later steps (fairness, map, Region
  Summary, assistant) must go through these functions rather than adding counts directly.
- "Problems without voice" panel is live in the 311 view. 65 tracts meet the 311 side (≥ 70th percentile of
  requests per 1k). The voice column reads "pending" because no letter has a tract yet; it fills in once
  `resolve_locations.py` (Milestone 4) writes `tract_id` on letters. Only percentiles are shown, never raw counts.

## Milestone 2 — simulated email channel (`scripts/ingest_emails.py`, 2026-10-23)

- **No emails are generated.** Per the user, the channel is exactly the user-supplied `sanjose_city_emails.csv`
  (164 rows: from, to, date, subject, body, attachment). The raw CSV lives only in gitignored
  `data/raw/emails/`; the committed fixture `public/data/fixtures/emails.json` is PII-free. Every row carries
  `channel="email"`, `mock=true`. `scripts/generate_mock_emails.py` is not used.
- **Simulated agenda items.** The CSV has no agenda item, so each email is assigned to one of 10 fictional items
  (`MOCK-26-901`…`910`: Terra Verde data center, streetlight reliability on Story/King, Alma Ave pavement repair,
  rental habitability, fourplex reform, rent-cap amendment, dumping/Coyote Creek, permitting, public safety budget,
  Blossom Hill rezoning) or to `MOCK-GEN` general correspondence. Assignment is weighted keyword scoring: strong cues
  that name the item count 3, thread-context cues count 1, highest wins, ties go to the earlier item. "renter" is
  deliberately not a cue because renters write about both zoning and rent. Result: streetlights 40, rent cap 39,
  Alma Ave 20, habitability 12, data center 11, fourplex 9, dumping 8, permitting 8, public safety 7,
  Blossom Hill 2, general 6 (job loss, medical debt, downtown flooding, cost of living, senior center, air quality).
  The item titles and meeting dates are invented and labeled simulated.
- **eComment-portal rows.** 6 rows were sent to an "eComments Portal" address by people who also emailed. They are
  kept with `submitted_via="ecomments_portal"` and `duplicate_of` pointing at the same sender's email on the same
  item (identity hash = sha256 of the sender address). They are the cross-channel dedup test.
- **PII.** Sender display names and addresses are dropped; `identity_hash` is kept for dedup. Body scrubbing removes
  email addresses, phone numbers, the sender's full name, signature lines containing sender-name tokens, and
  person-name lines right after a sign-off ("Respectfully,", "Atentamente,", "Trân trọng,"…) unless the line is a
  title ("Executive Director", "Coordinator"). Organization names are not personal data and are kept (an
  organization's subject line is never scrubbed). Audit on the output: 0 email addresses, 0 full sender names,
  0 signer lines. Recipient offices ("District 7 Council Office") are kept because they are public roles.
- `commenter_type`: `.org` sender or "(fictional)" organization → organization (6); property management →
  developer_or_counsel (1); else resident (157). Languages by langdetect: en 149, es 9, vi 6.
- **Attachments** (12) are recorded as metadata only (`kind`, `description`, `redacted=false`, `served=false`). The
  Wikimedia image URLs stay in the raw CSV; nothing is downloaded or displayed until the redaction step processes it.
- `public/data/inbox.json` feeds the Inbox panel: emails as received, newest first, sender shown as
  "[name and address removed at ingest]".
- Pipeline: step b in `scripts/data.sh`; `--offline` (or a missing raw CSV) rebuilds from the fixture.

## Milestone 4 — location resolution (`scripts/resolve_locations.py`, 2026-10-23)

- **Ladder:** address → neighborhood → zip → district → none; each comment stops at the first tier that resolves.
  `district` is an added tier for writers who state only their council district ("I am a resident of District 5"):
  `council_district` is set, `tract_id` stays empty. Otherwise `council_district` comes from the district containing
  the tract centroid; a stated district overrides it. Letters and emails run together into one `data/locations.csv`.
- **Coverage (honest, shown in the UI rather than hidden):**

  | tier | letters (271, real) | emails (164, simulated) | combined (435) |
  |---|---|---|---|
  | address | 9 (3.3%) | 8 (4.9%) | 17 (3.9%) |
  | neighborhood | 16 (5.9%) | 50 (30.5%) | 66 (15.2%) |
  | zip | 8 (3.0%) | 0 | 8 (1.8%) |
  | district only | 14 (5.2%) | 0 | 14 (3.2%) |
  | none | 224 (82.7%) | 106 (64.6%) | 330 (75.9%) |
  | **with a tract** | **33 (12.2%)** | **58 (35.4%)** | **91 (20.9%) in 28 of 215 tracts** |

  188 of the 271 letters are near-identical 25-081 campaign letters that say only "As a resident of San José".
  67 of the 91 located rows are `multi_tract=true`.
- **Address tier.** Signature addresses in the real letters are all organization offices (SVCN, SIREN, YWCA, a
  developer, the Chamber, the County), not homes; they stay at `address` precision as "where the commenter is
  based". Body addresses count only as an address block or after "I live at/on", because an address inside a
  sentence is usually the project site; the City Hall recipient block is skipped. Single addresses go to the US
  Census Geocoder (onelineaddress, Public_AR_Current / Current_Current → tract GEOID). Intersections are resolved by
  intersecting the two streets in San José GIS `OPN/OPN_OpenDataService/MapServer/60` (Streets, `FULLNAME`), major
  street types winning over Ct/Ln; crossings more than ~1 km apart are treated as ambiguous. A ~40-entry landmark
  gazetteer (coordinates from the Census geocoder on each landmark's address) resolves only after a proximity or
  residence cue, so "graduate of SJSU" never locates anyone. Results: 7 signature addresses, 1 letterhead, 4
  intersections (Story & King ×3, 5th & William), 5 landmarks (Kelley Park ×4, Diridon Station).
- **Neighborhood tier** needs context: a residence cue ("live in", "X resident", "my X block") or a sign-off line
  that is only a place counts strongly; a locative preposition counts weakly. Organization collisions ("X Union",
  "School District", "Washington D.C.", "SOMOS Mayfair") and negations ("I don't live there") are rejected.
  Token-aware fuzzy match at 85, every token ≥ 75; Spanish and Vietnamese cues supported. Generic city-GIS names
  without aliases are skipped when under 5 characters or a dictionary word. Primary tract = the listed tract with the
  largest population. The ingest's guessed neighborhood field is ignored for letters (it had false positives) and
  trusted for user-entered channels.
- **Item-title rule.** Places named in the agenda item title are ignored unless the comment has a first-person
  residence or proximity cue, so "streetlights along the Story Road corridor" does not locate a writer but "I cross
  King and Story every night" does.
- **Zip tier.** Census 2020 ZCTA–tract relationship file filtered to 95xxx / county 085 →
  `data/zcta_tract_crosswalk.csv`. People per overlap ≈ (overlap land area ÷ tract land area) × tract population,
  over our 215 tracts; zips with fewer than 500 estimated people in San José tracts, or following another city's
  name (95037 Morgan Hill), are treated as outside the city.
- **Privacy.** Raw addresses and intersections exist only in memory and in gitignored `data/raw/`.
  `data/geocode_cache.json` maps sha256(normalized query) → {tract_id, matched, source} and `locations.csv` carries no
  street text (asserted in code and tests). **Known limit:** an unsalted hash of a short address can be confirmed by
  hashing a guess. Every cached address today is an organization's office or a public intersection, so the risk is
  low; a secret salt kept in `data/raw/` is the fix before real resident addresses are ever cached.
- Thresholds (85 fuzzy, 92 landmarks, 45-character proximity window, 1 km crossing ambiguity, 500 people per zip)
  were tuned by hand on these 435 rows. Not resolved by design: single streets without a cross street ("traffic on
  Zanker", "the Alma Ave pothole") and the 30-mile Coyote Creek Trail.

## IBM Bob and Granite availability (correction 2, 2026-10-23)

- **Ollama** 0.40.9 installed via Homebrew and run as a brew service. The spec's `granite4.2:8b` tag does not exist in
  the Ollama library; `granite4.1:8b` (5.3 GB, the newest 8B Granite) is used, plus `nomic-embed-text`. Smoke test:
  ~82 tokens/s on this laptop.
- **IBM Bob Shell 2.0.6** installed from IBM's official script (`bob.ibm.com/download/bobshell.sh`, which downloads the
  tarball from IBM Cloud Object Storage and verifies its SHA-256). The global npm prefix needed root, so the same
  verified tarball was installed with `npm install -g --prefix ~/.local`; `bob` resolves from `~/.local/bin`.
- The CLI differs from the addendum's assumed form. Working headless form:
  `bob run --accept-license --mode agent --format json --max-turns N "<prompt>"` (also `-w <workspace>`, `--trust`,
  `--max-cost`). Output is one JSON line with `status`, `stats.task_id`, `stats.duration_ms`, `stats.session_costs`,
  and `last_message`.
- Without a key: `Error: Bob API key is required. Set BOB_API_KEY environment variable.` With a key but no license:
  `Error: A license agreement is required.` **The user supplied a Bob API key and explicitly accepted the IBM license
  (IBM Bob-Shell V2.0, 5900-BVU, L/N L-EBQG-R9G8MA) on 2026-10-23.** The key lives only in gitignored, owner-only
  `.env.local`. Test call `"reply with the word ok"` → `status: success`, `last_message: "ok"`, 2.1 s, $0.027.
- Budget guard: `BOB_MAX_RUNS=6` per pipeline run, `--max-cost 3` per Bob run. Every run is recorded in
  `public/data/provenance.json` and summarized in `BOB_USAGE.md`.

### Milestone 4 revision — locate the place a comment is about, not only the writer (2026-10-23)

- The user pointed out that the simulated emails were written with about 71 precise / 41 neighborhood / 52 none
  location mentions, while the first resolver gave 8 / 50 / 106. The first version located only the writer's
  residence and suppressed places named in the item title, which contradicted the spec ("the crosswalk at Story and
  King" should resolve to address precision). That rule is gone.
- **A location is the place a comment is about or where the writer is, whichever is finer.** New column
  `location_basis`: `residence` (residence/proximity cue, signature, organization letterhead, stated zip or district),
  `issue` (the place is the subject), or `both`. Within a tier, residence/both beats issue. Fairness participation
  ("who is heard") counts residence/both by default; the map and region counts use every located row.
- **New forms:** "Story and King", "King & Story", "Story/King", "First @ Alma St.", "corner of X and Y", "I cross X and
  Y", "X near Y", Spanish/Vietnamese connectors, and ranges ("King Road between Story and Tully" → midpoint of the two
  crossings). Street names are validated against all 11,962 San José GIS street names.
- **Single streets are anchored** (`location_source=street_anchor`, 56 rows), in order: a co-mentioned cross street; the
  nearest point to a co-mentioned neighborhood or landmark within 3 km; the segment nearest the centroid of the item's
  other located comments when they cluster within ~3 km (33 rows; this places the item, not the writer, so the UI
  labels every street anchor "street, approximate"); the street's same-named corridor (4 rows). `multi_tract` when the
  street crosses a tract line within 300 m.
- Fictional buildings and projects (Cedar Court, Terra Verde) are never geocoded by name; they resolve through the real
  street they are near or off, and that point carries to other comments on the same item, except for names that
  appear in the item title.
- **Result:**

  | tier | emails (164, simulated) | letters (271, real) | combined (435) |
  |---|---|---|---|
  | address | 77 (47.0%) | 19 (7.0%) | 96 (22.1%) |
  | neighborhood | 33 (20.1%) | 16 (5.9%) | 49 (11.3%) |
  | zip | 0 | 8 (3.0%) | 8 (1.8%) |
  | district only | 0 | 12 (4.4%) | 12 (2.8%) |
  | none | 54 (32.9%) | 216 (79.7%) | 270 (62.1%) |
  | with a tract | 110 (67.1%) | 43 (15.9%) | 153 in 36 tracts |

  Emails land at 77 / 33 / 54 against the user's 71 / 41 / 52 with general rules only, no per-row cases. Basis:
  emails residence 31, issue 68, both 11; letters residence 47, issue 8. Likely disagreements with the user's labels:
  a few cluster-anchored single streets ("traffic on Zanker") count as precise; Terra Verde emails that name only
  Alviso or North San José stay at neighborhood; "my place by 101", "by the creek", "my block" stay at none.
- Hand-picked thresholds: 3 km anchor radius, 5 km cluster cap, 3 km cluster spread, 300 m multi-tract buffer,
  fuzzy 85 with every word ≥ 80. Street geometry (public) is cached in gitignored `data/raw/sjgis/` so `--offline`
  reproduces the output exactly.
- Pipeline order fixed: `export_comments.py` (h) now runs before `fairness.py`, which reads the export; the offline
  flag reaches the location and Bob steps so `npm run demo` makes no network or paid calls.

### 311 categories mapped by IBM Bob (2026-10-23, supersedes the hand mapping)

- 311 rows are never sent to a model one by one (455,545 rows; the city already assigns a request type). Instead the
  97 distinct (Service Type, Category) combinations since 2025-07-01 (`data/taxonomy_311_combos.csv`, with counts and
  modal department) were given to IBM Bob in one run together with Bob's own voice taxonomy
  (`data/categories.json`). Bob assigned each combination one voice category key or `none`
  (`data/taxonomy_311_bob.json`, with a reason per row). Run: task `e88e0f6a081dcd03e85bd3fe4da06cfa`, 46.7 s,
  $0.19, 4 tool calls. Validated: 97 rows in order, every key exists in categories.json.
- Bob's result by rows: sanitation & environmental quality 287,165; streets & infrastructure 75,043; other 40,353;
  none 35,854; public safety & emergency response 14,076; code enforcement & permitting 2,971; housing &
  affordability 83. `none` covers billing, payments, accounts, e-billing, logins, property tax, parking permits,
  county/external routing, IT validation and community WiFi. Those rows stay in totals but are excluded from the
  problems layer, so 311 rates per 1k now count problem reports only. Bob's own calls stand as made (e.g. "Vehicle
  Concerns" → streets & infrastructure, "Encampment Concerns" → public safety).
- Because 311 and voice now share category keys, category-level comparisons are possible, but shares are still
  computed within each family and counts are never added across families. The earlier hand mapping
  (`data/taxonomy_311.csv`) is kept only as `category_hand` in the gitignored row-level CSV for comparison.

## Milestone 5 — categories and labels by IBM Bob (2026-10-23)

- **No preset categories.** Categories must come from the data via Bob. The `categorize-comments` skill states only how
  to derive a taxonomy (no category names or tie-breaks), and Bob derived 8 categories from the letters and emails on its own:
  Housing & Affordability Policy; Public Safety & Emergency Response; Streets & Infrastructure; Environment &
  Development Review; Code Enforcement & Permitting; Governance & Civic Rights; Sanitation & Environmental Quality;
  Other / General. A second Bob run added 3–5 subcategories under each from a digest of every unique comment; the
  top-level keys were frozen because the 311 mapping depends on them.
- **Bob labels every comment, not Granite** (user decision). `scripts/bob_label.py` collapses exact duplicates and
  MinHash form-letter campaigns (4 campaigns) so Bob labels 235 distinct texts in 6 batches of 40, 4 runs in parallel.
  Each label has category, subcategory, confidence, an evidence quote, stance and stance evidence, and is validated:
  keys must exist, the subcategory must sit under its category, and both quotes must be exact substrings of the
  comment. Invalid rows got one Bob retry batch. Campaign copies inherit the representative's label only after both
  quotes are re-located verbatim in the copy (rapidfuzz alignment ≥ 85 picks the copy's own text; 103 copies needed
  it because OCR noise differs between copies); the 8 copies that could not be aligned were labeled by Bob directly.
- **Result: all 435 comments labeled by Bob**, 0 by Granite, 0 by rules; every quote verified as
  an exact substring. Three batch files had invalid JSON because Bob copied quotes containing unescaped double quotes
  (report titles); they were repaired locally at no cost and the prompt now asks for escaping.
- **Cost:** $8.36 total across every Bob run in the project (probe, taxonomy $2.44, subcategories, 311 mapping, label,
  retry and copy batches), under the $10 cap. Per-run detail in `BOB_USAGE.md` and `data/bob_runs.json`.
- Granite 4.1 8B stays installed as the second-line fallback and the rule engine as the last; both write
  `engine` per row. `--offline` (the demo path) replays cached Bob labels and fails rather than calling Bob.
- Distribution (simulated emails / real letters): Streets & Infrastructure 61 / 1; Housing 51 / 2; Code Enforcement
  19 / 2; Environment & Development Review 13 / 0; Sanitation 9 / 0; Public Safety 7 / 5; Other 4 / 15; Governance &
  Civic Rights 0 / 246. The real letters are dominated by two governance matters (the immigrant-safety resolution
  campaign and the District 3 appointment). Stance: support 87 / 237, oppose 58 / 17, neutral 13 / 2, unclear 6 / 15.
- `data/labeled_sample_template.csv` has 100 comments with empty `true_category` / `true_stance` for a human audit;
  the classifier is **not yet audited** and no labels were fabricated.

## Milestone 6 — fairness with AI Fairness 360 (`scripts/fairness.py`, `web/fairness.js`, 2026-10-23)

- Unit: census tract (215). Per family, separately: favorable = per-1k rate above the citywide median over all 215
  tracts, computed once, stored in `public/data/fairness/meta.json`, never recomputed for a region. Voice =
  "comment participation above median"; Problems = "311 reporting above median". Never blended.
- Protected attributes (unprivileged side): low_income (median income < $141,289, the median of tract medians; default),
  majority_nonwhite (> 50%), renter_majority (> 50%), high_lep (limited-English households above the 75th percentile,
  17.6%). DI = P(fav | unprivileged) / P(fav | privileged); SPD = the difference. AIF360 0.6.1
  `BinaryLabelDatasetMetric` is the source of record; a pandas computation must match to 1e-9 or the script stops.
  Population-weighted variants use AIF360 instance weights (verified to match the weighted pandas formula).
- **311 (real, problem reports only, median 150.6 per 1k per year):** low_income DI 2.08 / SPD 0.35;
  majority_nonwhite 1.79 / 0.23; renter_majority 2.00 / 0.37; high_lep 1.71 / 0.30. Lower-income, majority-nonwhite,
  renter-majority and high-LEP tracts report problems to 311 above the median at 1.7–2.1× the rate of the others.
- **Voice (illustrative because simulated emails contribute):** 239 voices after duplicates and campaigns count once;
  participation counts residence/both-basis locations (77 rows). The voice median is 0, so "favorable" means any
  located comment. Most region-level voice views will return `not_enough_data` (< 5 tracts, < 2 tracts in a group, or
  < 10 voices). A letters-only (real) variant is exported alongside.
- Reweighing vs population weighting: AIF360 Reweighing balances how many tracts per group are favorable and gives
  each comment one of two group weights, so it reorders themes only when their comments split very differently by group
  (here: no rank changes). Population weighting (population share ÷ comment share, per tract) down-weights a few
  high-volume tracts regardless of group and reorders mid-ranked themes. Both are shown next to raw; neither is "the"
  fair ranking. Theme ranking is voice-only; 311 gets a category-by-volume table.
- Participation gap per tract: expected = population share × located voices; gap = (expected − observed)/expected.
  Underheard ranking = gap × relevance (1.0 inside an item's `affected_tracts` in staff-editable
  `public/data/affected.json`, 0.25 outside). Outreach briefs are template facts with generic channels; "unfair",
  "biased" and "apathetic" are banned and tests scan for them; briefs never describe what a tract's residents think.
- **Percentile fix.** With mid-rank ties every tract with zero located comments (184 of 215) shared voice percentile
  ~43, so "problems without voice" (problem ≥ 70th and voice ≤ 30th percentile) could never fire. Percentile is now the
  share of tracts with a strictly lower rate (`families.py`, `families.ts`, `web/fairness.js`, shared fixture
  regenerated), so silent tracts score 0. Result: 47 tracts are problems without voice; the top three
  (06085501402, 06085501601, 06085506305) sit at the 97th–99th 311 percentile with no located comment.
- `web/fairness.js` is a dependency-free port used for drawn regions; `web/fairness.test.mjs` checks it against the
  AIF360 outputs in `public/data/fairness/parity_fixtures.json` to 1e-9 (weighted and unweighted, every attribute).

## Milestone 7 — the CityLens map UI from the team's design (2026-10-23)

- The UI is the team's design (`docs/design/*.html`, `cvm.js`, `cvm.css`, kept verbatim for reference) running on
  pipeline data. `src/cvm/cvm.js` = a new data layer (`src/cvm/header.js`) + the design's map, panels, region drawing,
  fairness card, analytics, inspector and chat, with targeted edits. `npm run dev` opens it; `?screen=<key>` opens any
  of the design's screen states (01 … 08c); the plain data viewer moved to `#data`. Tailwind is not loaded on the map
  UI because its base styles restyle the design's inline SVG icons.
- **Everything synthetic in the design was replaced:** the generated comments, tract scatter, made-up 311 counts,
  canned quotes, invented email headers ("Lucretia", iPhone mailer), fake attachments and the pitch frames with
  hard-coded claims (the pitch pages were dropped). Picker items are IBM Bob's 8 sections plus "All sections"; the
  sidebar lists Bob's subsections; counts are unique comments (duplicates removed, campaign letters counted
  individually and tagged).
- `scripts/build_ui.py` writes `public/data/ui.json`: the 215 tracts with geometry, ACS 2020–2024 profile, council
  district, a display neighborhood from the city's neighborhoods layer, the city outline, and the attribute cutoffs
  from `fairness/meta.json`. Comments, 311 and fairness are read from their own files (one source of truth).
- **Rule changes forced by our rules, not the design's:**
  - Fairness "heard" = comment rate above the citywide median (as in `fairness.py`), replacing the design's
    40th-percentile "high-volume" rule. DI shows "—" when undefined.
  - Underheard with 311 = 311 rank − comment rank (0–100 percentiles of per-1,000 rates, share strictly below), and
    the tooltip shows both ranks plus the problems-without-voice flag; the design's share-difference mixed the two
    families. 311 rates are annualized.
  - Quotes everywhere are Bob's exact evidence quotes. Non-English comments are shown as written and labeled "not
    translated"; nothing is machine-translated or paraphrased.
  - Photos: listed from email metadata but withheld ("withheld until faces and plates are redacted") because no
    redaction step has run.
  - Outreach briefs state only ACS and pipeline facts; the design's claim about which languages are spoken was removed
    (we have no language-at-home table).
  - Unclear stance is a fourth stance with its own diamond shape, so stance is never color alone.
- **Chat** answers by retrieval over the ingested comments of the current section, narrowed to a drawn area or tract,
  citing comment ids; with no match it says so and points to matches in other sections. The LLM assistant bridge from
  the spec is not wired yet.
- Map dots: the design draws no comment dots (its dot layer is empty by design), so comments are shown through the
  choropleth, region panels and inspector; comment positions are still jittered inside their tract (seeded by
  comment id) for the pulse highlight, never at true coordinates.
- Bug found during wiring: an earlier test overwrote the label cache, so a cache replay restored only 427 of 435 Bob
  labels. `bob_label.py` now reuses every label Bob wrote in `data/bob_work/`; replay gives 435/435 Bob, no new calls.

## Milestone 7, round 2 — real assistant, analytics hierarchy, map key (2026-10-23)

- **Chat runs on IBM Bob as the app's assistant** (user decision; Bob no longer classifies anything). Dev-server bridge
  `server/assistant.mjs` (plugin in `vite.config.ts`) runs `bob run --mode agent --format json` with the skill
  `.bob/skills/app-analyst/SKILL.md`: a dictionary of every app data file, citation formats (`[[comment_id]]`,
  `[[metric:H5]]`, `[[file:path#key]]`), the voice/311 separation and simulated-email rules, a "how to use CityLens"
  guide, and an allowed action list (open a section, switch the map scheme, zoom to a tract, open analytics, open a
  comment, filter stance). The server validates every citation against the data files and every action against known
  ids; answers that make claims without valid citations are rejected and the client falls back to local search.
  Measured: 9–15 s and $0.07–0.15 per question. The canned demo conversation was removed; the panel starts empty with
  suggested questions. Static builds (no server) answer by local retrieval only and say so.
- **Bob budget** raised by the user to $50 total. The chat stops at `BOB_TOTAL_USD=50` (pipeline + chat spend) or
  `BOB_CHAT_DAILY_USD=10` per day; chat runs are logged without question text to gitignored `data/bob_chat_runs.json`.
- **Actionable labels.** Before the user's "no more classification" instruction arrived, one Bob pass labeled each
  comment actionable or not ($0.64; Bob pipeline total $8.99): 129 actionable, 306 not. Actionable = reports a
  specific problem or asks for a specific city action beyond a vote position. Kept because "actionable comment rate"
  is on the user's metric list; no further Bob classification runs.
- **New data:** household language by tract (ACS C16002 from the cached summary file: English only, Spanish, other
  Indo-European, Asian & Pacific Island, other) and MTC Equity Priority Communities 2024 (ACS 2018–2022, 2020 tracts,
  via the city's mirror `DOT/DOT_AllReferenceLayers/MapServer/12`): 59 of our tracts are High/Higher/Highest, 1 tract
  is missing from MTC's data. Anonymous participant numbers (P0001…) are derived from the dedup hash in the export; the
  hash itself never reaches the browser.
- **Team settings** in `public/data/config.json` (not chosen by the app or AI): under-represented = comment share
  below 0.5× population share; stance shown only for policy sections (housing, governance, environment & development,
  public safety, code enforcement); low confidence < 0.8; "small sample" warning under 10 comments.
- **Analytics** (City analytics button, or Open analytics from a region or tract): area info first (residents,
  households, comments, 311 reports and rate, median income as High/Average/Low with % vs the city tract median,
  English-only and limited-English households, renters, non-white share, Equity Priority status, council district),
  then — citywide: public input (comments without copies, submissions incl. copies, location unknown, actionable),
  comments by section and subsection, support/opposition for policy sections, volume over time by channel,
  representation (under-represented tract rate, residents in them, Equity Priority comment vs population share),
  geographic concentration per section, 311 rate and mix, AI label confidence; per tract or area: comments and
  representation ratio, issue share vs city with gap, languages (households vs comments, ratio), who is writing
  (distinct writers, comments per writer, form-letter share, actionable, organizations), 311, AI confidence.
- **Map key**: the legend has a "Map key · all colors" section explaining Voice, Problems and Underheard together.
  The pop card shows residents (and households for a tract) first.

### Analytics and pop card, round 3 (2026-10-23)

- Analytics are organized as questions with a one-sentence answer first: About this area (residents, households,
  English-only and limited-English households, renters, median income level, Equity Priority status) → Is this area
  being heard? → What do people write about? (sections with top subsections, here vs city, support/oppose for policy
  sections only) → What do people report to 311? → Who is writing? (writers, comments per writer, form letters,
  organizations, simulated share, languages vs households) → citywide only: When did comments arrive? and Is each
  issue local or citywide? → How much should you trust these numbers? → Who are we not hearing from? (with the full
  tract table collapsed). The side column holds only the mini map and the name; all facts moved into the main panel.
- The map pop card leads with residents, English-only households, renters and median income (each with the citywide
  value), followed by one small line each for comments vs expected, the top issue and 311 reports.
- The top-bar section picker was briefly replaced by a summary line and then restored at the user's request.

### Analytics dashboard, round 4 (2026-10-23)

- Rebuilt as a dashboard with visual hierarchy, following the dataviz method: a facts strip (residents, English-only,
  limited-English, renters, median income level, Equity Priority), four KPI tiles (comments, representation ratio
  with a bullet marked at 1.0 — or, citywide, the share of residents where nothing was heard — 311 reports per 1,000 a
  year with a monthly sparkline and change vs city, actionable share with change vs city), then charts: a donut of
  sections with a labeled legend (count, share, top subsection), here-vs-citywide paired bars, diverging
  support/oppose bars for policy sections, a monthly 311 line (area vs city, per 1,000 residents, one axis), 311 mix
  bars, language bars (comments vs households), writer stats, citywide timeline and locality, trust meters, and
  missing voices. Every mark has a hover tip.
- Section colors use the dataviz reference categorical palette in a fixed order (slot = position in
  categories.json), so a section keeps its color everywhere. Validator: all hard checks pass on white (worst adjacent
  CVD ΔE 9.1, normal-vision ΔE 19.6); three hues are below 3:1 contrast, so every chart ships visible labels.
  Change arrows use ink, not status colors, because more or fewer reports is not good or bad by itself.

### Generated constituent emails for geographic coverage (2026-10-23)

- 385 more simulated emails, generated for the demo, live in `data/raw/emails/sanjose_city_emails_generated.csv`
  (the user's CSV is untouched). `ingest_emails.py` reads both files. Generated rows have `generated=true`,
  `generated_by` and `source_file`/`source_row` in emails_raw.csv, inbox.json, the email fixture and
  comments.json. All are `mock=true` and use fictional names and example.* addresses.
- Their geography is shaped to follow the usual participation pattern in San José. Homeowner and high-income
  tracts write in at about twice the per-resident rate of middle tracts. Usual under-heard areas get few emails, and
  more of those are short and in Spanish or Vietnamese. A few less obvious spots get none: tracts picked from the data
  for a high 311 rate plus many renters or limited-English households (Starbird, Blackford, Cadillac Winchester,
  Windmill Springs, Hoffman-Via Monte), and the Tasman/Zanker apartment tracts. Census and 311 numbers are not
  changed.
- Every located generated email resolves to its intended tract with a residence basis, through a real intersection
  or a neighborhood name. Generated rows are excluded from the item-cluster and named-place passes in
  `resolve_locations.py`, so the locations of the original 435 comments do not change.
- Labels and actionable flags come from IBM Bob (`bob_label.py`, `bob_actionable.py`), with the same exact-quote
  validation as every other comment.

## Second batch of simulated emails (479, written per section by small AI writers)

To give every section enough comments to analyze, four Haiku writers each drafted 120 emails from a fixed template
(section, subcategory, language, persona, issue, detail, ask, stance). The topic mix follows real San José demand: the
city's own 311 data is dominated by junk pickup, graffiti, vehicle complaints and illegal dumping, then streetlights,
encampments and potholes, so sanitation, code enforcement and public safety get the most new emails. Writers were not
allowed to name places or people. `scripts/mock_emails/batch2.py` rejects any that do (and any repeated openings), then adds a
location sentence, sender, date and recipient, placing emails with the same per-resident census tract weights as the first batch.
IBM Bob labels them like every other comment (section, subsection, stance, exact evidence quote, actionable flag).
All rows are `mock=true, generated=true`.
