#!/usr/bin/env bash
# Regenerate the build agent's simulated emails and rebuild everything downstream. No IBM Bob calls (budget 0).
# usage: bash scripts/mock_emails/chain.sh
set -e
cd "$(dirname "$0")/../.."
S=scripts/mock_emails
PY=.venv/bin/python
PYTHONHASHSEED=0 $PY $S/gen.py $S $S/overrides.json | cut -c1-160
PYTHONHASHSEED=0 $PY $S/batch2.py $S | tail -1
$PY scripts/ingest_emails.py 2>&1 | head -1
$PY scripts/resolve_locations.py 2>&1 | grep -E "\[email\]"
$PY $S/verify.py $S | tail -6
BOB_BUDGET_USD=0 $PY scripts/bob_label.py >/dev/null 2>&1
$PY $S/labels.py $S
BOB_BUDGET_USD=0 $PY scripts/bob_label.py 2>&1 | tail -1
BOB_BUDGET_USD=0 $PY scripts/bob_actionable.py 2>&1 | tail -1
for s in export_comments fairness build_ui metrics; do $PY scripts/$s.py >/dev/null 2>&1; done
$PY $S/report.py 2>&1 | grep -v "aif360\|pandas"
