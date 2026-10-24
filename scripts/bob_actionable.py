#!/usr/bin/env python3
"""Step e2: one yes/no label per voice comment — is it actionable? — by IBM Bob within the remaining budget.

actionable = the comment reports a specific problem the city could investigate (a broken light, a pothole, a
habitability failure, dumping at a place) or asks for a specific city action beyond simply supporting or opposing
the agenda item (repair, inspection, enforcement, funding a named fix, cleanup, a named policy change).
A bare vote position ("vote no", "I support this") is not actionable on its own.

Same units as bob_label.py (duplicates and campaign copies collapsed); copies inherit their representative's label.
Budget: the project-wide Bob cap BOB_BUDGET_USD (default 10) counts every Bob run in data/bob_runs.json. Units that do
not fit are written to data/bob_work/actionable_todo.jsonl and must be labeled by the build agent into
data/bob_work/actionable_agent.json ({comment_id: {"actionable": bool, "reason": str}}); those rows carry
engine "build-agent". Output: data/actionable.csv (comment_id, actionable, reason, engine, bob_task_id).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bob_label as B  # noqa: E402

OUT = ROOT / "data" / "actionable.csv"
TODO = B.WORK / "actionable_todo.jsonl"
AGENT = B.WORK / "actionable_agent.json"
BATCH = 60
CAP = 1200


def prompt(bp: Path, out: Path) -> str:
    return (f"Read {bp.relative_to(ROOT)} (one public comment per line: comment_id, text). For EVERY line decide whether "
            "the comment is ACTIONABLE: true if it reports a specific problem the city could investigate (a broken "
            "streetlight, a pothole, no hot water, dumping at a place, a dangerous crossing) or asks for a specific city "
            "action beyond simply supporting or opposing the agenda item (a repair, an inspection, enforcement, a cleanup, "
            "funding a named fix, a named policy change or condition). A bare vote position or general opinion is false. "
            f"Write {out.relative_to(ROOT)} as a valid JSON array, same order, of objects "
            '{"comment_id": "...", "actionable": true|false, "reason": "max 8 words"}. Escape any double quote inside a '
            "string. Do not run scripts or modify other files. Reply with the number of objects written.")


def main() -> int:
    raw = B.C.load_voice()
    units, follower_of, *_ = B.build_units(raw)
    env = B.load_env()
    B.WORK.mkdir(exist_ok=True)
    labels: dict[str, dict] = {}
    for f in sorted(B.WORK.glob("act_labels_*.json")):  # reuse anything already written
        try:
            for o in B.load_labels_file(f):
                if isinstance(o, dict) and isinstance(o.get("actionable"), bool):
                    labels[o["comment_id"]] = {"actionable": o["actionable"], "reason": str(o.get("reason", ""))[:80],
                                               "engine": "bob", "bob_task_id": ""}
        except Exception:  # noqa: BLE001
            pass
    todo = [u for u in units if u["comment_id"] not in labels]
    left = []
    for i in range(0, len(todo), BATCH):
        rows = todo[i:i + BATCH]
        if B.spent() + 0.35 > B.BUDGET:
            left.extend(rows)
            continue
        n = 50 + i // BATCH
        bp, out = B.WORK / f"act_batch_{n:02d}.jsonl", B.WORK / f"act_labels_{n:02d}.json"
        with bp.open("w") as f:
            for r in rows:
                f.write(json.dumps({"comment_id": r["comment_id"], "text": r["text"][:CAP]}, ensure_ascii=False) + "\n")
        rec = B.bob(prompt(bp, out), f"actionable_batch_{n:02d}", env, max_cost=min(1.0, B.BUDGET - B.spent()), max_turns=8)
        try:
            arr = B.load_labels_file(out)
        except Exception as e:  # noqa: BLE001
            arr = []
            B.log(f"  batch {n}: unreadable ({e!r})")
        got = {o.get("comment_id"): o for o in arr if isinstance(o, dict) and isinstance(o.get("actionable"), bool)}
        for r in rows:
            o = got.get(r["comment_id"])
            if o:
                labels[r["comment_id"]] = {"actionable": o["actionable"], "reason": str(o.get("reason", ""))[:80],
                                           "engine": "bob", "bob_task_id": rec.get("task_id") or ""}
            else:
                left.append(r)
        B.log(f"  actionable batch {n}: {len(got)}/{len(rows)}, ${float(rec.get('session_costs') or 0):.3f}, total ${B.spent():.2f}")
    agent = json.loads(AGENT.read_text()) if AGENT.exists() else {}
    for cid, o in agent.items():
        if cid not in labels:
            labels[cid] = {"actionable": bool(o["actionable"]), "reason": str(o.get("reason", ""))[:80],
                           "engine": "build-agent", "bob_task_id": ""}
    pending = [r for r in left if r["comment_id"] not in labels]
    with TODO.open("w") as f:
        for r in pending:
            f.write(json.dumps({"comment_id": r["comment_id"], "text": r["text"][:CAP]}, ensure_ascii=False) + "\n")
    rows_out = []
    for r in raw.to_dict("records"):
        src = r["comment_id"]
        while src in follower_of and src not in labels:
            src = follower_of[src]
        lab = labels.get(src)
        rows_out.append({"comment_id": r["comment_id"], "actionable": "" if lab is None else lab["actionable"],
                         "reason": "" if lab is None else lab["reason"], "engine": "" if lab is None else lab["engine"],
                         "bob_task_id": "" if lab is None else lab["bob_task_id"], "inherited_from": src if src != r["comment_id"] else ""})
    pd.DataFrame(rows_out).to_csv(OUT, index=False)
    eng = pd.DataFrame(rows_out)["engine"].value_counts().to_dict()
    B.log(f"actionable: {eng}; pending for build agent: {len(pending)} units ({TODO.relative_to(ROOT)}); Bob total ${B.spent():.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
