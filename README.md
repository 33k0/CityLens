# CityLens: Civic Voice Map (San José)

Civic Voice Map turns the civic needs of San José into a live map and shows where the issues cluster and what the
people need. AI Fairness 360 corrects for who reports vs. who lives there, and an officials-only chatbot answers
questions with cited sources.

Hackathon MVP for SpartHill 2026 at SJSU. City council staff receive hundreds of public comments per agenda item.
Civic Voice Map ingests them, classifies each by category and stance, resolves each to a census tract (never finer),
plots them on a map of San José, and overlays census demographics to show **which neighborhoods are underheard** on
each item, with fairness metrics from IBM AI Fairness 360.

**Status:** scaffold, real Legistar letters ingest, census tracts + ACS, and the real 311 problems layer are done.
The app renders every ingested letter and the 311 aggregates. Voice (letters, email, site) and Problems (311) are
separate families and are never summed. The map, fairness panels and assistant are later milestones.

## Demo

```bash
npm install
python3.11 -m venv .venv && .venv/bin/pip install aif360 && .venv/bin/pip install pandas geopandas shapely pyproj httpx beautifulsoup4 lxml rapidfuzz datasketch langdetect python-dotenv pillow pytest
npm run demo          # offline: committed fixtures -> dev server at http://localhost:5173
npm run demo:warm     # re-inventories Legistar and downloads/parses letter PDFs (1 req/s; OCR needs `brew install tesseract`)
npm test              # vitest + pytest
npm run build         # static build, zero keys needed
```

No API keys are needed for anything that exists today. See `.env.example` for the optional ones.

## Data sources & provenance

- **Written comments (real):** the emailed **Letters from the Public** attached to City Council agenda items on
  Legistar, 2025–2026, via the Legistar Web API (`webapi.legistar.com/v1/sanjose`). Inventory on 2026-10-23: 405
  letter PDFs on 300 matters across 82 council meetings. **Currently ingested: 15 PDFs on 10 matters → 271 letters**
  (local PDFs; `scripts/ingest_legistar.py` can inventory and download more). 93% of those letters are OCR'd scans
  (early-2025 bundles); location coverage by tier is reported after Milestone 4. Sender names, emails and phone
  numbers are removed at ingest; raw PDFs and signature addresses stay in gitignored `data/raw/`.
- **311 service requests (real):** San José Open Data "311 Service Request Data" (CC0), 2025 and 2026 yearly CSVs,
  window 2025-07-01 onward: 455,545 requests, 224,694 of them located to one of the city's 215 census tracts by
  point-in-polygon (the other half have no coordinates in the source; mostly garbage-service requests). Coordinates
  are discarded after the join; no address exists in the source.
- **Tracts / demographics:** TIGER 2024 cartographic tracts clipped to the city limits (215 tracts), ACS 5-year 2024.
- **Emails:** mock channel (Milestone 2), every record `"mock": true`, kept as a test fixture only if real letters
  exceed ~150 (they do).

Details and every assumption: [DECISIONS.md](DECISIONS.md).

## Responsible-AI card, architecture, IBM tooling, impact evaluation

Written as the milestones land (Milestone 8). Tract count and coverage by precision tier will be reported here.
