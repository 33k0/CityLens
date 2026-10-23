# CityLens: Civic Voice Map (San José)

Civic Voice Map turns the civic needs of San José into a live map and shows where the issues cluster and what the
people need. AI Fairness 360 corrects for who reports vs. who lives there, and an officials-only chatbot answers
questions with cited sources.

Hackathon MVP for SpartHill 2026 at SJSU. City council staff receive hundreds of public comments per agenda item.
Civic Voice Map ingests them, classifies each by category and stance, resolves each to a census tract (never finer),
plots them on a map of San José, and overlays census demographics to show **which neighborhoods are underheard** on
each item, with fairness metrics from IBM AI Fairness 360.

**Status: Milestones 0–1 done** (scaffold + real Granicus eComments scraper). The app currently renders every
ingested comment; the map, fairness panels and assistant are later milestones.

## Demo

```bash
npm install
python3.11 -m venv .venv && .venv/bin/pip install aif360 && .venv/bin/pip install pandas geopandas shapely pyproj httpx beautifulsoup4 lxml rapidfuzz datasketch langdetect python-dotenv pillow pytest
npm run demo          # offline: committed fixtures -> dev server at http://localhost:5173
npm run demo:warm     # re-scrapes Granicus (1 req/s, ~1 min) then starts the dev server
npm test              # vitest + pytest
npm run build         # static build, zero keys needed
```

No API keys are needed for anything that exists today. See `.env.example` for the optional ones.

## Data sources & provenance

- **eComments (real):** `sanjose.granicusideas.com`, 4 City Council agenda items chosen by comment count
  (2020-04-07 Rent Suspension; 2022-01-25 Gun Harm Reduction Ordinance; 2023-06-06 RV Communities / Emergency
  Interim Housing; 2023-06-06 Berryessa Lease). **685 comments**, every one matching the site's declared count.
  Commenter names, emails and addresses are dropped at ingest; raw HTML stays in gitignored `data/raw/`.
  The site does not publish the neighborhood or zip fields, so eComment locations come from the text (Milestone 4).
- **Emails:** mock, Milestone 2, every record carries `"mock": true`.

Details and every assumption: [DECISIONS.md](DECISIONS.md).

## Responsible-AI card, architecture, IBM tooling, impact evaluation

Written as the milestones land (Milestone 8). Tract count and coverage by precision tier will be reported here.
