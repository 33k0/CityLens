#!/usr/bin/env python3
"""Step e (labeling): IBM Bob labels every voice comment with category, subcategory, stance and exact evidence.

Flow
  1. subcategories  One Bob run reads Bob's own taxonomy (data/categories.json) plus a digest of the corpus and adds
                    2-5 subcategories under each category. Top-level keys are frozen (311 depends on them).
  2. units          Exact duplicates and form-letter campaign copies are collapsed (classify.py's dedup + MinHash),
                    so Bob labels one representative per group. Copies inherit the label only if both quotes are
                    exact substrings of the copy; otherwise the copy is labeled on its own.
  3. batches        ~40 units per batch file, several Bob runs in parallel, each writing labels_NN.json.
  4. validate       Enum + exact-substring checks (classify.validate_label) + subcategory belongs to its category.
                    Invalid rows get one Bob retry batch. Anything still invalid -> Granite -> rule engine.
  5. budget         Total Bob spend (all steps, from data/bob_runs.json) is capped at BOB_BUDGET_USD (default 10).
                    When the cap would be crossed, remaining batches are written to data/bob_work/unlabeled.jsonl for
                    the build agent to label by hand (engine "build-agent"); nothing is silently skipped.

Outputs: data/categories.json (subcategories added), data/classifications.csv, data/campaigns.json,
data/labeled_sample_template.csv, data/bob_runs.json, public/data/provenance.json, data/classify_cache.json (bob
labels cached by text hash so --offline replays with zero calls).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import classify as C  # noqa: E402

DATA = ROOT / "data"
WORK = DATA / "bob_work"
CATS = DATA / "categories.json"
RUNS = DATA / "bob_runs.json"
BUDGET = float(os.environ.get("BOB_BUDGET_USD", "10"))
BATCH = 40
TEXT_CAP = 2500
PARALLEL = 4
PROMPT_VERSION = "bob-label-v1"
log = lambda s: print(s, file=sys.stderr, flush=True)  # noqa: E731


# ------------------------------------------------------------------ bob plumbing
def load_env() -> dict:
    env = dict(os.environ)
    p = ROOT / ".env.local"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    if not env.get("BOB_API_KEY"):
        raise SystemExit("BOB_API_KEY is not set (.env.local)")
    return env


def redact(s: str) -> str:
    return re.sub(r"bob_prod_[A-Za-z0-9_-]+", "[key]", s)


def runs_log() -> dict:
    return json.loads(RUNS.read_text()) if RUNS.exists() else {"runs": []}


def spent() -> float:
    return round(sum(float(r.get("session_costs") or 0) for r in runs_log()["runs"]), 4)


def record_run(rec: dict) -> None:
    d = runs_log()
    d["runs"].append(rec)
    RUNS.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")


def bob(prompt: str, kind: str, env: dict, max_cost: float = 2.0, max_turns: int = 12) -> dict:
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    t0 = time.time()
    p = subprocess.run(["bob", "run", "--accept-license", "--mode", "agent", "--format", "json", "-w", str(ROOT), "--trust",
                        "--max-turns", str(max_turns), "--max-cost", str(max_cost), prompt],
                       capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL, timeout=1800)
    out = redact(p.stdout + p.stderr)
    result = {}
    for line in out.splitlines():
        if line.startswith("{") and '"type":"result"' in line.replace(" ", ""):
            try:
                result = json.loads(line)
            except json.JSONDecodeError:
                pass
    stats = result.get("stats", {})
    rec = {"engine": "bob", "kind": kind, "status": result.get("status", f"exit {p.returncode}"),
           "started_at": started, "seconds": round(time.time() - t0, 1), "exit_code": p.returncode,
           "task_id": stats.get("task_id"), "duration_ms": stats.get("duration_ms"),
           "session_costs": stats.get("session_costs"), "tool_calls": stats.get("tool_calls"),
           "last_message": (result.get("last_message") or out[-400:])[:600]}
    record_run(rec)
    return rec


# ------------------------------------------------------------------ step 1: subcategories
def digest(raw: pd.DataFrame, units: list[dict]) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    lines = ["# Voice corpus digest (one entry per unique comment; campaigns and duplicates collapsed)\n"]
    for item, g in pd.DataFrame(units).groupby("item"):
        lines.append(f"\n## {item} — {g['item_title'].iloc[0]}\n")
        for r in g.itertuples():
            t = re.sub(r"\s+", " ", f"{r.subject} | {r.text}")[:350]
            lines.append(f"- [{r.comment_id}] {t}")
    p = WORK / "corpus_digest.md"
    p.write_text("\n".join(lines))
    return p


def ensure_subcategories(raw, units, env) -> None:
    cats = json.loads(CATS.read_text())
    if all(c.get("subcategories") for c in cats["categories"]):
        log("subcategories already present")
        return
    keys = [c["key"] for c in cats["categories"]]
    dp = digest(raw, units)
    rec = bob(f"Read data/categories.json (your voice-comment taxonomy) and {dp.relative_to(ROOT)} (every unique comment, "
              "grouped by agenda item). Add a 'subcategories' array to EVERY category in data/categories.json: 2 to 5 "
              "subcategories per category, each {\"key\": snake_case, \"label\": short plain-language label, "
              "\"description\": one sentence}, derived from what residents actually wrote (each subcategory should fit "
              "at least 2 real comments; the catch-all category may use broad subcategories). Subcategory keys must be "
              "unique across the whole file. Do NOT rename, add, remove or reorder the top-level categories or change "
              "any existing field; only add 'subcategories'. Also add a top-level field \"subcategories_added_on\" with "
              "today's date. Do not modify any other file. Reply with the subcategory keys per category.",
              "subcategories", env, max_cost=2.5, max_turns=10)
    after = json.loads(CATS.read_text())
    got = [c["key"] for c in after["categories"]]
    if got != keys:
        CATS.write_text(json.dumps(cats, indent=2, ensure_ascii=False) + "\n")
        raise SystemExit(f"Bob changed top-level category keys ({got}); restored the original file")
    missing = [c["key"] for c in after["categories"] if not c.get("subcategories")]
    if missing:
        raise SystemExit(f"Bob did not add subcategories for {missing}: {rec['last_message'][:300]}")
    after.setdefault("bob_task_ids", []).append(rec["task_id"])
    CATS.write_text(json.dumps(after, indent=2, ensure_ascii=False) + "\n")
    log(f"subcategories added by Bob (task {rec['task_id']}, ${rec['session_costs']})")


# ------------------------------------------------------------------ step 2: units
def build_units(raw: pd.DataFrame):
    dup, dup_stats = C.identity_duplicates(raw)
    camp, campaigns = C.find_campaigns(raw.assign(duplicate_of=raw["comment_id"].map(lambda c: dup.get(c, ""))))
    reps = {c["campaign_id"]: c["representative_comment_id"] for c in campaigns}
    by_text: dict[str, str] = {}
    units, follower_of = [], {}
    for r in raw.to_dict("records"):
        cid = r["comment_id"]
        if dup.get(cid):
            follower_of[cid] = dup[cid]
            continue
        cmp_ = camp.get(cid)
        if cmp_ and reps[cmp_] != cid:
            follower_of[cid] = reps[cmp_]
            continue
        norm = C.norm_ws(r["text"]).lower()
        if norm in by_text:
            follower_of[cid] = by_text[norm]
            continue
        by_text[norm] = cid
        units.append(r)
    return units, follower_of, dup, dup_stats, camp, campaigns


# ------------------------------------------------------------------ step 3/4: label batches
def text_hash(r: dict) -> str:
    return hashlib.sha256(f"{PROMPT_VERSION}\x1f{r.get('subject', '')}\x1f{r['text']}".encode()).hexdigest()


def write_batch(n: int, rows: list[dict]) -> Path:
    p = WORK / f"batch_{n:02d}.jsonl"
    with p.open("w") as f:
        for r in rows:
            f.write(json.dumps({"comment_id": r["comment_id"], "language": r.get("language") or "",
                                "item_title": r.get("item_title", ""), "subject": r.get("subject", ""),
                                "text": r["text"][:TEXT_CAP]}, ensure_ascii=False) + "\n")
    return p


def label_prompt(bp: Path, out: Path, errors: dict | None = None) -> str:
    fix = ""
    if errors:
        fix = (" These rows were rejected before; fix exactly these problems: "
               + "; ".join(f"{k}: {', '.join(v)}" for k, v in list(errors.items())[:60]) + ".")
    return (f"Read data/categories.json (categories, each with subcategories) and {bp.relative_to(ROOT)} (one public "
            "comment per line: comment_id, language, item_title, subject, text). For EVERY line, label the comment and "
            f"write {out.relative_to(ROOT)} as a JSON array (same order) of objects with exactly these fields: comment_id; "
            "category (a top-level category key); subcategory (a subcategory key belonging to that category); "
            "confidence (0-1); evidence_quote (5-25 words copied character-for-character from the text field, the phrase "
            "that best justifies the category); stance (support|oppose|neutral|unclear: the writer's position on the "
            "agenda item or the action they ask the city to take); stance_evidence (copied character-for-character from "
            "the text; empty string only when stance is neutral or unclear). The file must be valid JSON: escape every double "
            "quote inside a string value as \\\" (quotes often contain titles in quotation marks). Read non-English comments in their own "
            "language and quote them in that language. Never paraphrase quotes, never quote the subject line. Do not "
            "run scripts and do not modify any other file. When done reply with the number of objects written." + fix)


FIELD_LINE = re.compile(r'^(\s*"(?:evidence_quote|stance_evidence|reason|subcategory|category|comment_id|stance)":\s*")(.*)("\s*,?\s*)$')


def load_labels_file(path: Path) -> list:
    """Parse Bob's labels file; if it is invalid JSON because quotes were copied with unescaped inner double quotes
    (e.g. a report title in quotation marks), escape them line by line and parse again."""
    txt = path.read_text()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        fixed = []
        for line in txt.splitlines():
            m = FIELD_LINE.match(line)
            if m:
                inner = re.sub(r'(?<!\\)"', r'\\"', m.group(2))
                line = m.group(1) + inner + m.group(3)
            fixed.append(line)
        return json.loads("\n".join(fixed))


def align_quote(quote: str, text: str, min_score: float = 85.0) -> str | None:
    """Campaign copies differ by OCR noise. Find the passage of THIS copy that best matches the representative's
    quote and return it verbatim (an exact substring of the copy), or None if nothing matches closely enough."""
    from rapidfuzz import fuzz
    al = fuzz.partial_ratio_alignment(quote, text, score_cutoff=min_score)
    if not al:
        return None
    span = text[al.dest_start:al.dest_end].strip()
    return span if span and C.find_span(span, text) else None


def seed_from_work(units: list[dict], cats: dict, cache: dict, chash: str) -> int:
    """Reuse labels Bob already wrote in data/bob_work (e.g. a run whose files needed quote repair)."""
    by_id = {u["comment_id"]: u for u in units}
    runs = {r.get("kind"): r.get("task_id") for r in runs_log()["runs"]}
    n = 0
    for f in sorted(WORK.glob("labels_*.json")):
        try:
            arr = load_labels_file(f)
        except Exception as e:  # noqa: BLE001
            log(f"  {f.name}: still unreadable after repair ({e!r})")
            continue
        num = f.stem.split("_")[1]
        task = runs.get(f"label_batch_{num}") or runs.get(f"retry_batch_{num}") or ""
        for o in arr:
            u = by_id.get(o.get("comment_id")) if isinstance(o, dict) else None
            if not u or cache.get(f"bob:{chash}:{text_hash(u)}"):
                continue
            lab, errs = validate(o, cats, u["text"][:TEXT_CAP])
            if lab:
                lab["bob_task_id"] = task
                cache[f"bob:{chash}:{text_hash(u)}"] = lab
                n += 1
    return n


def validate(obj: dict, cats: dict, text: str) -> tuple[dict | None, list[str]]:
    lab, errs = C.validate_label(obj, cats, text)
    subs = {c["key"]: {s["key"] for s in c.get("subcategories", [])} for c in cats["categories"]}
    sub = obj.get("subcategory") if isinstance(obj, dict) else None
    if isinstance(obj, dict) and obj.get("category") in subs and sub not in subs[obj["category"]]:
        errs = errs + [f"subcategory {sub!r} is not under {obj['category']}"]
    if errs:
        return None, errs
    lab["subcategory"] = sub
    return lab, []


def run_batches(batches: list[tuple[int, list[dict]]], cats, env, kind="label") -> tuple[dict, dict, list]:
    """Returns ({comment_id: label}, {comment_id: errors}, leftover_rows_not_attempted_for_budget)."""
    labels, errors, leftover = {}, {}, []
    est = 0.9  # per-batch cost guess until we have real numbers
    pending = list(batches)
    with cf.ThreadPoolExecutor(max_workers=PARALLEL) as ex:
        futs = {}
        while pending or futs:
            while pending and len(futs) < PARALLEL:
                if spent() + est * (len(futs) + 1) > BUDGET:
                    for _, rows in pending:
                        leftover.extend(rows)
                    log(f"!! budget: ${spent():.2f} spent of ${BUDGET:.2f}; {len(leftover)} rows left for the build agent")
                    pending = []
                    break
                n, rows = pending.pop(0)
                bp, out = write_batch(n, rows), WORK / f"labels_{n:02d}.json"
                out.unlink(missing_ok=True)
                errs_for = {r["comment_id"]: errors.get(r["comment_id"], []) for r in rows} if kind == "retry" else None
                futs[ex.submit(bob, label_prompt(bp, out, errs_for), f"{kind}_batch_{n:02d}", env, 2.0, 12)] = (n, rows, out)
            if not futs:
                break
            done, _ = cf.wait(futs, return_when=cf.FIRST_COMPLETED)
            for f in done:
                n, rows, out = futs.pop(f)
                rec = f.result()
                cost = float(rec.get("session_costs") or 0)
                est = max(est * 0.5 + cost * 0.5, 0.2) if cost else est
                try:
                    arr = load_labels_file(out)
                except Exception as e:  # noqa: BLE001
                    arr = []
                    log(f"  batch {n:02d}: no readable labels file ({e!r}); status {rec['status']}")
                by_id = {o.get("comment_id"): o for o in arr if isinstance(o, dict)}
                ok = 0
                for r in rows:
                    o = by_id.get(r["comment_id"])
                    if o is None:
                        errors[r["comment_id"]] = ["missing from Bob's output"]
                        continue
                    lab, errs = validate(o, cats, r["text"][:TEXT_CAP])
                    if lab:
                        lab["bob_task_id"] = rec["task_id"]
                        labels[r["comment_id"]] = lab
                        errors.pop(r["comment_id"], None)
                        ok += 1
                    else:
                        errors[r["comment_id"]] = errs
                log(f"  {kind} batch {n:02d}: {ok}/{len(rows)} valid, ${cost:.3f}, {rec['seconds']}s (total spent ${spent():.2f})")
    return labels, errors, leftover


# ------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="replay cached Bob labels only; no calls")
    ap.add_argument("--plan", action="store_true", help="print unit/batch counts and exit")
    args = ap.parse_args()
    t0 = time.time()
    raw = C.load_voice()
    raw["language"] = [C.row_language(r) for r in raw.to_dict("records")]
    units, follower_of, dup, dup_stats, camp, campaigns = build_units(raw)
    log(f"{len(raw)} voice comments -> {len(units)} units to label ({len(follower_of)} copies inherit), {len(campaigns)} campaigns")
    if args.plan:
        print(json.dumps({"rows": len(raw), "units": len(units), "batches": -(-len(units) // BATCH), "spent": spent()}))
        return 0

    cache = C.load_cache()
    env = None if args.offline else load_env()
    if not args.offline:
        ensure_subcategories(raw, units, env)
    cats = json.loads(CATS.read_text())
    chash = C.categories_hash(cats)

    if WORK.exists():  # every row, not only units: campaign copies Bob labeled on their own are reused too
        seeded = seed_from_work(raw.to_dict("records"), cats, cache, chash)
        if seeded:
            C.save_cache(cache)
            log(f"reused {seeded} valid Bob labels already written in {WORK.relative_to(ROOT)}")
    labels: dict[str, dict] = {}
    todo = []
    for r in units:
        hit = cache.get(f"bob:{chash}:{text_hash(r)}")
        if hit:
            labels[r["comment_id"]] = hit
        else:
            todo.append(r)
    log(f"{len(labels)} units from cache, {len(todo)} to send to Bob")
    if todo and args.offline:
        raise SystemExit(f"--offline: {len(todo)} units have no cached Bob label; run a warm build")

    leftover: list[dict] = []
    if todo:
        batches = [(i // BATCH + 1, todo[i:i + BATCH]) for i in range(0, len(todo), BATCH)]
        got, errors, leftover = run_batches(batches, cats, env)
        labels.update(got)
        bad = [r for r in todo if r["comment_id"] in errors]
        if bad and spent() < BUDGET - 0.5:
            log(f"retrying {len(bad)} invalid rows in one Bob batch")
            g2, errors2, left2 = run_batches([(90 + i // BATCH, bad[i:i + BATCH]) for i in range(0, len(bad), BATCH)],
                                             cats, env, kind="retry")
            labels.update(g2)
            leftover.extend(left2)
            errors = {k: v for k, v in errors2.items()}
        for r in todo:
            if r["comment_id"] in labels:
                cache[f"bob:{chash}:{text_hash(r)}"] = labels[r["comment_id"]]
        C.save_cache(cache)

    # copies whose inherited quotes cannot be aligned to their own text get labeled on their own
    def inherit_ok(cid):
        src = cid
        while src in follower_of and src not in labels:
            src = follower_of[src]
        lab = labels.get(src)
        if not lab or src == cid:
            return bool(lab)
        text = by_id_all[cid]["text"]
        return all(not (lab.get(f) or "") or C.find_span(lab[f], text) or align_quote(lab[f], text) for f in ("evidence_quote", "stance_evidence"))
    by_id_all = {r["comment_id"]: r for r in raw.to_dict("records")}
    orphans = [by_id_all[c] for c in follower_of if not inherit_ok(c)]
    if orphans:
        for r in orphans:
            hit = cache.get(f"bob:{chash}:{text_hash(r)}")
            if hit:
                labels[r["comment_id"]] = hit
        need = [r for r in orphans if r["comment_id"] not in labels]
        if need and not args.offline:
            log(f"{len(need)} campaign copies differ too much from their representative; labeling them on their own")
            g3, _e3, left3 = run_batches([(80, need)], cats, env, kind="copies")
            labels.update(g3)
            leftover.extend(left3)
            for r in need:
                if r["comment_id"] in g3:
                    cache[f"bob:{chash}:{text_hash(r)}"] = g3[r["comment_id"]]
            C.save_cache(cache)
        for r in orphans:  # own label wins over inheritance
            follower_of.pop(r["comment_id"], None) if r["comment_id"] in labels else None

    # rows Bob could not label (invalid twice) -> rule engine; budget leftovers -> build agent file
    rules = C.RuleEngine(cats)
    left_ids = {r["comment_id"] for r in leftover}
    if leftover:
        WORK.mkdir(exist_ok=True)
        with (WORK / "unlabeled.jsonl").open("w") as f:
            for r in leftover:
                f.write(json.dumps({"comment_id": r["comment_id"], "text": r["text"][:TEXT_CAP]}, ensure_ascii=False) + "\n")
    agent_labels = json.loads((WORK / "agent_labels.json").read_text()) if (WORK / "agent_labels.json").exists() else {}

    by_id = {r["comment_id"]: r for r in raw.to_dict("records")}
    engines, rows_out = Counter(), []
    for r in raw.to_dict("records"):
        cid = r["comment_id"]
        src = cid
        while src in follower_of and src not in labels:
            src = follower_of[src]
        lab, eng = labels.get(src), "bob"
        aligned = False
        if lab and src != cid:  # inherited: both quotes must be exact substrings of THIS copy
            lab = dict(lab)
            for fld in ("evidence_quote", "stance_evidence"):
                q = lab.get(fld) or ""
                if not q or C.find_span(q, r["text"]):
                    continue
                span = align_quote(q, r["text"])
                if span:
                    lab[fld], aligned = span, True
                else:
                    lab = None
                    break
        if lab is None and cid in agent_labels:
            lab, eng = agent_labels[cid], "build-agent"
        if lab is None:
            rl = rules.classify(r["text"], r.get("subject", ""), r.get("item_title", ""))
            subs = next(c.get("subcategories", []) for c in cats["categories"] if c["key"] == rl["category"])
            lab, eng = {**rl, "subcategory": subs[0]["key"] if subs else "", "bob_task_id": ""}, "fallback"
            if cid in left_ids:
                eng = "pending-build-agent"
        engines[eng] += 1
        rows_out.append({"comment_id": cid, "channel": r["channel"], "item": r["item"], "category": lab["category"],
                         "subcategory": lab.get("subcategory", ""), "confidence": lab["confidence"],
                         "evidence_quote": lab["evidence_quote"], "stance": lab["stance"],
                         "stance_source": {"bob": "bob", "build-agent": "build-agent"}.get(eng, "rule"),
                         "stance_evidence": lab["stance_evidence"], "language": r["language"], "engine": eng,
                         "model": {"bob": "IBM Bob Shell", "build-agent": "build agent (Claude)"}.get(eng, C.RULES_MODEL),
                         "bob_task_id": lab.get("bob_task_id", ""), "inherited_from": src if src != cid else "",
                         "quote_aligned": aligned,
                         "campaign_id": camp.get(cid, ""), "duplicate_of": dup.get(cid, "")})
    out = pd.DataFrame(rows_out)
    out.to_csv(C.OUT_CSV, index=False)
    for c in campaigns:
        c["stance"] = dict(Counter(out.set_index("comment_id")["stance"].reindex(c["comment_ids"]).dropna()))
    C.CAMPAIGNS_PATH.write_text(json.dumps({"method": "MinHash/LSH over 5-word shingles, verified on exact shingle sets "
                                            "(see scripts/classify.py); voice family only",
                                            "counting_rule": "Downstream counts a campaign once by default.",
                                            "campaigns": campaigns}, indent=2, ensure_ascii=False) + "\n")
    C.write_sample(out, raw)
    bob_runs = [r for r in runs_log()["runs"] if r.get("kind", "").startswith(("label", "retry", "subcategories"))]
    C.upsert_provenance([{
        "step": "classify", "engine": "cache" if args.offline else "bob", "model": "IBM Bob Shell",
        "reason": "per-comment labels by IBM Bob in batches; Granite/rules only for rows Bob could not label validly",
        "started_at": datetime.fromtimestamp(t0, timezone.utc).isoformat(timespec="seconds"),
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "wall_seconds": round(time.time() - t0, 1),
        "counts": {"rows": len(out), "units_labeled": len(units), "inherited": int((out["inherited_from"] != "").sum()),
                   "by_engine": dict(engines), "bob_spent_total_usd": spent()},
        "bob_task_ids": [r["task_id"] for r in bob_runs if r.get("task_id")], "prompt_version": PROMPT_VERSION,
        "categories_source": cats.get("source")}])
    log(f"done in {time.time() - t0:.0f}s: {dict(engines)}; Bob spent ${spent():.2f} total")
    print(json.dumps({"by_engine": dict(engines), "spent": spent(), "leftover": len(leftover)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
