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

## Milestone 1 — Granicus eComments scraper

### Site inspection (2026-10-23, `sanjose.granicusideas.com`)

- Meeting index: `/meetings`, `/meetings?scope=past` (788 meetings, ids 2413–5879, 2016 → 2026). Each meeting lists
  agenda items at `/meetings/<id>-<slug>/agenda_items?page=N` (15 items per page). Item pages are
  `/meetings/<id>-<slug>/agenda_items/<24-hex>-<slug>?page=N` with **20 comments per page**.
- **Public comment markup** (`ul.comments > li[id^=ecomment_]`): avatar, `a.user` display name, `span.timeago`
  (absolute "at October 20, 2026 at 10:43am PDT" for recent comments, relative "over 3 years ago" for older ones),
  `.pull-right label.label` with Support / Oppose / Neutral (sometimes absent), `div.comment_body` text.
- **Fields that are public:** name, posted time, position, text.
  **Not rendered anywhere public:** email, address, city, state, zip, **neighborhood**. The form collects them but the
  page does not show them, so `neighborhood` and `zip` are empty for every eComment and location resolution for this
  channel must come from the text (Milestone 4 landmark/street extraction). The main document expected "likely
  neighborhood"; it is not there.
- **Names are dropped** at parse time; they exist only inside `data/raw/` (gitignored). Tests assert no name or
  `/profile/` id reaches any record.
- Comment ids on the site are Mongo ObjectIds; the first 4 bytes are the creation time. `received_at` is derived from
  that when the page only gives a relative time (every comment on the chosen items). Verified against an item with an
  absolute timestamp.

### Item selection — chosen by comment count

- **Meetings after January 2024 on this instance carry almost no eComments** (ids 5216→5862 gap; the five most recent
  council meetings total 2 comments). The city appears to have paused the eComment tool and reopened it in
  September 2026. So "recent" was traded for volume, which the prompt makes the priority (≥200 comments).
- Per-meeting counts from the past list (top): 3842 (2020-04-07) 1670, 4602 (2022-01-25) 1227, 3849 (2020-04-21) 777,
  4379 (2021-08-24) 667, 5022 (2023-06-06) 407. Per-item counts inside those; housing / land use / public safety items:

  | item | title | declared | scraped | exact repeats |
  |---|---|---|---|---|
  | 2023-06-06_8.4 | 23-842 City Initiatives Roadmap: RV Communities Support Parking and Emergency Interim Housing | 273 | 273 | 32 |
  | 2023-06-06_8.5 | 23-843 Berryessa Lease Agreement (heard with 8.4) | 119 | 119 | 11 |
  | 2020-04-07_8.3 | 20-452 Rent Suspension | 148 | 148 | 9 |
  | 2022-01-25_4.1 | 22-045 Gun Harm Reduction Ordinance | 145 | 145 | 2 |
  | **total** | | **685** | **685** | **54** |

  Skipped: 4379 "Vaccine Mandate" (639, placeholder-titled item) and 4602 "4. PUBLIC SAFETY SERVICES" (260, a section
  header that collected gun-ordinance comments); 3842's remaining 1,500 comments sit on procedural COVID-notice items.
  Both can be added with `--item-url`.
- Stance totals: oppose 651, support 19, neutral 3, unclear (no label) 12. The chosen items are heavily one-sided; that
  is the real data and is itself a participation signal.
- Per-neighborhood counts cannot be logged at scrape time (field not public); they will be logged after Milestone 4.
- `comment_id = "G" + sha1(item_id + text)[:8]` per spec. 54 submissions repeat another submission's text exactly within
  the same item (form letters). They are kept as separate records (they are distinct people) with `-2`, `-3` suffixes and
  `duplicate_of` pointing at the first, so Milestone 5 campaign detection has the full count. The viewer can collapse them.
- Rate limit 1 req/s, project User-Agent, exponential backoff on 429/5xx. Full scrape of the 4 items = 36 page fetches.
- `public/data/fixtures/ecomments.json` is the committed, PII-free fixture (same payload as `comments_raw.json`);
  `--offline` and any network failure load it. `--from-raw` re-parses cached HTML without fetching.
