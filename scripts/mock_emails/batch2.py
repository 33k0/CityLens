# -*- coding: utf-8 -*-
"""Second batch of simulated emails: text from small AI writers (Haiku), one JSONL file per pair of sections in
scripts/mock_emails/batch2/*.jsonl, placed in census tracts and signed here.

Each JSONL row gives section, subcategory, lang, persona, length, subject, issue, detail[], ask, stance, actionable.
Writers never name places or people; this script adds the location sentence (the same templates as gen.py, which
resolve_locations.py is known to resolve), greeting, sign-off, a fictional sender and a date. Census tracts are drawn
with gen.py's per-resident weights, so homeowner, high-income areas still write in more per resident than renter,
low-income and limited-English areas. Labels come from the brief each writer was given (section, subcategory,
stance); the evidence quote is the issue sentence, an exact substring of the email.

usage: batch2.py SCRATCH_DIR   (writes data/raw/emails/sanjose_city_emails_generated_batch2.csv and SCRATCH_DIR/side2.json)
"""
import csv, json, random, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# reuse gen.py's tract weights, location pools and sender helpers without running its email loop
src = (HERE / "gen.py").read_text()
src = src[:src.index("# ------------------------------------------------------------------ located emails")]
sys.argv = [str(HERE / "gen.py"), str(HERE), str(HERE / "overrides.json")]
G = {"__file__": str(HERE / "gen.py"), "__name__": "gen_prefix"}
exec(compile(src, "gen.py", "exec"), G)
P, ui, ints, alloc = G["P"], G["ui"], G["ints"], G["alloc"]
rng = random.Random(20261024)
G["rng"].seed(20261024)

OUT = G["ROOT"] / "data/raw/emails/sanjose_city_emails_generated_batch2.csv"
KEYS = ["section", "subcategory", "lang", "persona", "length", "subject", "issue", "detail", "ask", "stance", "actionable",
        "actionable_reason"]
cats = json.loads((G["ROOT"] / "data/categories.json").read_text())
SUBS = {c["key"]: {s["key"] for s in c.get("subcategories", [])} for c in cats["categories"]}
# only real names: "<Name> Street/Ave/…", known San José places, ZIPs, emails, links (generic "my street" is fine)
PLACE = re.compile(r"\b[A-Z][a-z]+ (?:Street|St|Avenue|Ave|Blvd|Boulevard|Road|Rd|Drive|Dr|Expressway|Creek|Park|Way|Lane)\b|"
                   r"\b(?:San Jos[eé]|Coyote|Guadalupe|Alviso|Willow Glen|Evergreen|Berryessa|Almaden|Cambrian|Japantown|Story Road|"
                   r"Tully|Capitol|King Road|Santa Clara|District \d)\b|\b95\d{3}\b|@|https?://")


def rows_in():
    seen = set()
    for f in sorted((HERE / "batch2").glob("*.jsonl")):
        for n, line in enumerate(f.read_text().splitlines()):
            if not line.strip():
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                print(f"skip {f.name}:{n} bad json"); continue
            why = ([k for k in KEYS if k not in o] and "missing keys") or \
                  (o["section"] not in SUBS and "section") or (o["subcategory"] not in SUBS.get(o["section"], ()) and "subcategory") or \
                  (o["lang"] not in ("en", "es", "vi", "zh", "tl") and "lang") or \
                  (o["stance"] not in ("support", "oppose", "neutral") and "stance") or \
                  (not isinstance(o["detail"], list) and "detail") or \
                  (not (8 <= len(o["issue"]) <= 400) and "issue length") or \
                  (PLACE.search(" ".join([o["subject"], o["issue"], o["ask"], *o["detail"]])) and "names a place")
            head = " ".join(o["issue"].lower().split()[:6])
            if not why and head in seen:
                why = "repeat opening"
            if why:
                print(f"skip {f.name}:{n} {why}"); continue
            seen.add(head)
            yield o


def pick_tract(o):
    """gen.py's per-resident targets, nudged by tenure and home language so writers land where they plausibly live."""
    w = {}
    for tid, a in alloc.items():
        t = ui[tid]
        x = a + 0.15
        x *= t["renter"] + 0.1 if o["persona"] == "tenant" else (1 - t["renter"]) + 0.1
        lang = t.get("lang") or {}
        if o["lang"] == "es":
            x *= lang.get("spanish", 0) + 0.02
        elif o["lang"] in ("vi", "zh", "tl"):
            x *= lang.get("asian_pacific", 0) + 0.02
        w[tid] = x
    ids = list(w)
    return rng.choices(ids, weights=[w[i] for i in ids])[0]


rows, side = [], []
for k, o in enumerate(rows_in()):
    L = o["lang"]
    has_pool = L in P.LOC_INT
    method = rng.choices(["int", "nb", "none"], [45, 25, 30])[0] if has_pool else "none"
    tid = pick_tract(o) if method != "none" else None
    loc = None
    Y = rng.choice([3, 5, 7, 9, 12, 16, 20, 27])
    if method == "int":
        pi = G["pick_int"](tid, f"b2#{k}")
        if pi is None:
            method = "nb"
        else:
            a, b, raw = pi
            pool = P.LOC_INT_OWNER if (L == "en" and o["persona"] == "business") else P.LOC_INT[L]
            if L == "en" and o["persona"] == "tenant":
                pool = [s for s in pool if "homeowner" not in s and "My house" not in s]
            if L == "en" and o["persona"] == "owner":
                pool = [s for s in pool if "rent an" not in s]
            loc = rng.choice(pool).format(A=a, B=b, Y=Y)
    if method == "nb":
        nbs = G["pretty_nbs"](tid)
        if nbs:
            pool = P.LOC_NB[L] if o["persona"] != "tenant" else [s for s in P.LOC_NB[L] if "homeowner" not in s]
            loc = rng.choice(pool).format(N=rng.choice(nbs), Y=Y, YR=rng.choice([1999, 2004, 2010, 2015, 2018]))
        else:
            method, tid = "none", None
    details = o["detail"][: {"short": 0, "medium": 1, "long": 2}.get(o["length"], 1)]
    p1 = ([loc, o["issue"]] if rng.random() < 0.6 else [o["issue"], loc]) if loc else [o["issue"]]
    greet = rng.choice(P.GREET.get(L, P.GREET["en"])) if L in P.GREET else ""
    so = rng.choice(P.SIGNOFF.get(L, [""])) if L in P.SIGNOFF else ""
    display, addr = G["person"](L if L in ("en", "es", "vi") else "en")
    body = "\n\n".join(([greet] if greet else []) + [" ".join(p1 + details), o["ask"]])
    body += "\n\n" + "\n".join(([so] if so else []) + [G["signer"](display, L)])
    date, _ = G["rand_date"]("batch2")
    district = ui[tid].get("district") if tid else None
    rows.append({"from": f"{display} <{addr}>", "to": G["to_field"](L if L in ("es", "vi") else "en", district), "date": date,
                 "subject": o["subject"], "body": body, "attachment": ""})
    pol = o["stance"] in ("support", "oppose")
    side.append({"row": len(rows) - 1, "tract": tid, "method": method, "lang": L, "persona": o["persona"],
                 "label": {"category": o["section"], "subcategory": o["subcategory"], "confidence": round(rng.uniform(0.8, 0.93), 2),
                           "evidence_quote": o["issue"], "stance": o["stance"], "stance_evidence": o["ask"] if pol else ""},
                 "actionable": {"actionable": bool(o["actionable"]), "reason": str(o.get("actionable_reason", ""))[:80]}})

with OUT.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["from", "to", "date", "subject", "body", "attachment"])
    w.writeheader()
    w.writerows(rows)
(Path(sys.argv[1]) / "side2.json").write_text(json.dumps(side, ensure_ascii=False, indent=1))
from collections import Counter
print(len(rows), "emails;", Counter(s["method"] for s in side), Counter(s["lang"] for s in side),
      Counter(s["label"]["category"] for s in side))
