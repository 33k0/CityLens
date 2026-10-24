# CityLens (San José)

CityLens shows San José council staff who they are hearing from and who they are not. It maps public comments, 311
reports and police calls by census tract, compares them with who lives there, and flags neighborhoods that report
many problems but rarely write in. An IBM Bob assistant answers questions about the data with a source on every claim.

Built by team **Civics** for SpartHill 2026 at SJSU.

- **Live app:** https://city-lens-livid.vercel.app
- **Project write-up:** [docs/DEVPOST.md](docs/DEVPOST.md)

## What's in the app

- **Map views:** Voice (comments per 1,000 residents), Problems (311 reports or police calls per 1,000 residents,
  filterable by report type) and Underheard (many problems, few comments). Side-by-side shows two views, or two
  places, at once.
- **Who gets heard:** IBM AI Fairness 360 results in plain language ("Renter neighborhoods are heard about half as
  often as homeowner ones").
- **Regions:** draw one or more areas, open a council district or neighborhood, or compare two places.
- **Analytics:** for the city, a region or one census tract, including a "How much to trust these numbers" card and a
  "Who we are not hearing from" table.
- **IBM Bob assistant:** answers with cited, server-checked sources and can drive the map.

## Run it locally

Needs Node 22+ and Python 3.11.

```bash
npm install
python3.11 -m venv .venv && .venv/bin/pip install aif360 pandas geopandas shapely pyproj scipy httpx beautifulsoup4 lxml rapidfuzz datasketch langdetect python-dotenv pillow pdfplumber pytesseract pytest
npm run dev           # app at http://localhost:5173, using the committed data in public/data
npm test              # vitest + pytest
npm run build         # static build
```

The map, analytics and fairness panels work with no keys. The staff chat needs IBM Bob:

1. Install IBM Bob Shell (`npm install` installs the official `bobshell` package; see https://bob.ibm.com/docs/shell)
   and accept its license yourself.
2. Copy `.env.example` to `.env.local` (gitignored) and set `BOB_API_KEY`.

Without a key, the chat falls back to a keyword search over the comments.

**Deploying to Vercel:** `api/assistant.mjs` runs the same chat server as a serverless function. Set `BOB_API_KEY`
(and optionally `BOB_API_KEY_BACKUP`) and `BOB_LICENSE_ACCEPTED=true` in the project's environment variables.

## Rebuilding the data

```bash
npm run data          # full pipeline (needs the raw downloads in data/raw/, which are gitignored)
npm run data:offline  # replays committed fixtures and cached labels; no network, no Bob calls
```

`scripts/data.sh` runs the steps in order: letters (OCR), emails, census tracts, 311, 311 report types, police calls,
location matching, IBM Bob labels, export, fairness (AIF360), map layer, metrics, and the chat's data files.

## Data sources

| Data | Source | Used for |
|---|---|---|
| Letters from the Public, 2025–2026 (real) | San José City Council on Legistar | Comments: 271 letters, 195 unique; names, emails and phones removed at ingest |
| Simulated constituent emails | Team-supplied (164) and AI-generated (864) | Filling out every section and the whole city; marked `mock` and "simulated" everywhere |
| 311 Service Requests (real, CC0) | San José Open Data | 217,415 problem reports placed in census tracts, July 2025 to October 2026 |
| Police Calls for Service (real, CC0) | San José Open Data | 352,566 calls, same months; 88% placed in census tracts |
| ACS 5-year 2020–2024 | U.S. Census Bureau | Population, renters, income, race, household language |
| TIGER 2024 | U.S. Census Bureau | 215 census tracts clipped to city limits |
| Equity Priority Communities 2024 | MTC | Equity flags |
| Districts, neighborhoods, street centerlines | San José GIS | Regions and address matching |

Comments, 311 reports and police calls are separate families: they are compared only through per-resident rates and
rankings, never added together. Nothing finer than a census tract is ever stored or shown.

## How IBM tools are used

- **IBM Bob** derived the comment taxonomy, labeled all 1,299 comments with an exact evidence quote (rejected if not
  word-for-word), mapped 311 service types and police call types to the same sections, and runs the staff assistant
  with custom skills (`.bob/skills/`) and rules (`.bob/rules/civic-data.md`). Details: [BOB_USAGE.md](BOB_USAGE.md).
- **IBM AI Fairness 360** computes disparate impact and statistical parity for low-income, majority non-white,
  renter-majority and high limited-English census tracts, cross-checked against pandas (`scripts/fairness.py`).

## Repository map

- `src/cvm/`: the map app (D3), chat client and styles
- `server/assistant.mjs`, `api/assistant.mjs`: the chat server (dev and Vercel)
- `scripts/`: the data pipeline
- `public/data/`: the data the app reads
- `docs/METRICS.md`: every metric with its formula · `DECISIONS.md`: design decisions and why

## Limitations

- 1,022 of 1,217 unique comments are simulated, so comment patterns demonstrate the method rather than real findings.
- 56% of comments contain enough location detail to be placed in a census tract.
- 311 reports and police calls measure reporting, not need; police calls are calls, not crimes.
- AI labels are checked by code (exact quotes) but not yet reviewed by staff.
