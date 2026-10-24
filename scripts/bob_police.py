#!/usr/bin/env python3
"""Step a5: IBM Bob labels every SJPD call type -> data/taxonomy_police_bob.json.

Like taxonomy_311_bob.json for 311: Bob reads the 198 distinct call types in the police calls-for-service files (same
months as 311, with counts) and assigns each one
  group   - one of the eight plain call groups staff see (violence, theft_property, traffic, disturbance, welfare,
            suspicious, alarm, other)
  section - the CityLens section it relates to (a key from data/categories.json) or "none"
  reason  - eight words or fewer
Code then checks every row (known call type, valid group, valid section); ingest_police.py uses Bob's labels and only
falls back to keyword rules for a call type Bob did not label. Spend counts toward BOB_BUDGET_USD like every Bob run.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bob_label as B  # noqa: E402

FILES = [ROOT / "data/raw/police" / f"policecalls{y}.csv" for y in (2025, 2026)]
OUT = ROOT / "data" / "taxonomy_police_bob.json"
GROUPS = ["violence", "theft_property", "traffic", "disturbance", "welfare", "suspicious", "alarm", "other"]


def main() -> int:
    months = set(json.loads((ROOT / "public/data/requests_311_by_tract.json").read_text())["months"])
    cnt = Counter()
    for f in FILES:
        with open(f, encoding="utf-8", errors="replace") as fh:
            for r in csv.DictReader(fh):
                if (r.get("REPORT_DATE") or "")[:7] in months:
                    cnt[(r.get("CALL_TYPE") or "").strip()] += 1
    cats = json.loads(B.CATS.read_text())["categories"]
    keys = [c["key"] for c in cats]
    B.WORK.mkdir(exist_ok=True)
    inp = B.WORK / "police_call_types.jsonl"
    out = B.WORK / "police_types_labels.json"
    with inp.open("w") as fh:
        for t, n in cnt.most_common():
            fh.write(json.dumps({"call_type": t, "count": n}) + "\n")
    sections = "; ".join(f"{c['key']} = {c['label']}" for c in cats)
    prompt = (f"Read {inp.relative_to(ROOT)} (one San José Police call-for-service type per line, with how many calls it had). "
              f"For EVERY line assign: group = one of {', '.join(GROUPS)} (violence = assaults, weapons, robbery, sexual "
              "assault; theft_property = theft, burglary, vandalism, fraud; traffic = stops, collisions, parking, reckless "
              "driving; disturbance = disturbances, noise, fights, fireworks; welfare = welfare checks, mental health, "
              "medical, missing persons, intoxication; suspicious = suspicious people or vehicles, trespassing, prowlers; "
              "alarm = alarms; other = administrative or anything else), and section = the CityLens section it most relates "
              f"to, one of: {sections}; or \"none\" if it relates to none. Write {out.relative_to(ROOT)} as a valid JSON "
              'array, same order, of objects {"call_type": "...", "group": "...", "section": "...", "reason": "max 8 words"}. '
              "Copy call_type exactly. Do not run scripts or modify other files. Reply with the number of objects written.")
    env = B.load_env()
    out.unlink(missing_ok=True)
    rec = B.bob(prompt, "police_call_types", env, max_cost=min(1.5, B.BUDGET - B.spent()), max_turns=10)
    arr = B.load_labels_file(out)
    labels, bad = {}, []
    for o in arr if isinstance(arr, list) else []:
        t = o.get("call_type") if isinstance(o, dict) else None
        if t in cnt and o.get("group") in GROUPS and (o.get("section") in keys or o.get("section") == "none"):
            labels[t] = {"group": o["group"], "section": o["section"], "reason": str(o.get("reason", ""))[:80], "count": cnt[t]}
        else:
            bad.append(o)
    OUT.write_text(json.dumps({"engine": "IBM Bob Shell", "bob_task_id": rec.get("task_id"), "call_types": len(cnt),
                               "labeled": len(labels), "unlabeled": [t for t in cnt if t not in labels],
                               "labels": labels}, ensure_ascii=False, indent=1))
    B.log(f"police call types: Bob labeled {len(labels)}/{len(cnt)} ({sum(v['count'] for v in labels.values())} of "
          f"{sum(cnt.values())} calls); {len(bad)} rejected; ${float(rec.get('session_costs') or 0):.3f}; Bob total ${B.spent():.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
