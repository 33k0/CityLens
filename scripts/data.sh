#!/usr/bin/env bash
# `npm run data`: build-time pipeline, addendum order a->h. Steps that are not built yet are skipped.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
[ -x "$PY" ] || PY=python3
run() { if [ -f "scripts/$1" ]; then echo "== $1"; "$PY" "scripts/$1" "${@:2}"; else echo "-- $1 (not built yet, skipped)"; fi; }
# a  Legistar crawl is NOT part of the default pipeline (local PDFs + items.csv instead; see ingest_letters.py --crawl)
run ingest_letters.py "$@"             # a2 (split local Letters PDFs into comment rows)
run ingest_emails.py "$@"              # b  (simulated email channel from the user-supplied CSV; no generation)
run build_tracts.py "$@"              # c
run ingest_311.py "$@"                 # a3 (311 service requests -> per-tract counts; needs tracts from c)
run p311_types.py                     # a4 (311 per census tract by service type, for filtering the Problems map)
run resolve_locations.py "$@"         # d
run bob_label.py "$@"                  # e  (IBM Bob labels every voice comment; --offline replays the cache; run_bob.mjs rebuilds the taxonomy on request)
run export_comments.py                # h  (voice export: letters + email + site, joined with locations and classifications)
run fairness.py                       # f/g (reads the export, so it runs last)
run build_ui.py                       # j  (tract layer for the map UI)
run metrics.py                        # i  (every metric in docs/METRICS.md -> public/data/metrics.json)
run chat_context.py                   # k  (tract profiles, area index, associations for the staff chat)
