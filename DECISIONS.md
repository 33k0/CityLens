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
