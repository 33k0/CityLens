#!/usr/bin/env bash
# `npm run data`: build-time pipeline, addendum order a->h. Steps that are not built yet are skipped.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
[ -x "$PY" ] || PY=python3
run() { if [ -f "scripts/$1" ]; then echo "== $1"; "$PY" "scripts/$1" "${@:2}"; else echo "-- $1 (not built yet, skipped)"; fi; }
run ingest_ecomments.py "$@"          # a
run generate_mock_emails.py           # b
run build_tracts.py                   # c
run resolve_locations.py              # d
if [ -f scripts/run_bob.mjs ]; then echo "== run_bob.mjs"; node scripts/run_bob.mjs; else echo "-- run_bob.mjs (not built yet, skipped)"; fi   # e
run fairness.py                       # f/g
run export_comments.py                # h
