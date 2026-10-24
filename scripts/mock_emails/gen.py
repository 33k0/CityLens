# -*- coding: utf-8 -*-
"""Generate data/raw/emails/sanjose_city_emails_generated.csv (+ scratch side files with intended tract and labels).

usage: gen.py SCRATCH_DIR [overrides.json]
overrides.json: {"<slot key>": {"skip_int": [...pairs...], "force": "nb"|"int"|"none"}} used to repair slots that did not
resolve to their intended tract.
"""
import csv, json, random, re, sys
from datetime import datetime, timedelta
from pathlib import Path

SCR = Path(sys.argv[1])
sys.path.insert(0, str(SCR))
import pools as P

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/emails/sanjose_city_emails_generated.csv"
OVR = json.loads(Path(sys.argv[2]).read_text()) if len(sys.argv) > 2 and Path(sys.argv[2]).exists() else {}
rng = random.Random(20261023)

import pandas as pd
tiers = pd.read_csv(SCR / "tiers.csv", dtype={"id": str}).set_index("id")
ints = json.loads((SCR / "ints.json").read_text())
nbp = json.loads((SCR / "nb_prim.json").read_text())
ui = {t["id"]: t for t in json.loads((ROOT / "public/data/ui.json").read_text())["tracts"]}

BAD_NB = re.compile(r"\band\b|corridor|area|High|School|Elementary|Mobile|\bDr\b|Road|Expressway|Avenue|Ave\b|Blvd|Street|"
                    r"Country Club|Winery|Flea|/|Stevens Creek|Valley Medical|Coyote Creek|\bSt\b", re.I)


def pretty_nbs(tid):
    return [n for n in nbp.get(tid, []) if not BAD_NB.search(n)]


# ------------------------------------------------------------------ tiers (data-driven)
B_TIER = set(tiers.index[(tiers.B) & (tiers.priv < 0.6)])
# less-obvious under-heard spots, picked from the data: high 311 percentile and renter/LEP-heavy, outside the usual-suspect
# neighborhoods (see report); plus the North San José / Rincon apartment tracts (renter share 0.82-1.0)
C_TIER = {"06085506305", "06085511915", "06085506504", "06085503212", "06085506304",
          "06085505012", "06085505013", "06085505014", "06085505015"}
order = [t for t in tiers.sort_values("priv", ascending=False).index if t not in B_TIER and t not in C_TIER]
A_TIER = order[:58]
alloc = {}
# per-resident targets: homeowner/high-income tracts write in at roughly twice the rate of middle tracts; usual
# under-heard tracts get few (some none); the data-picked less-obvious spots get none
ZERO_USUAL = {"06085501402", "06085501601", "06085501602", "06085501800", "06085501502", "06085503112", "06085503710",
              "06085501401", "06085503711", "06085503713"}
ONE_USUAL = {"06085503113", "06085503708", "06085501000", "06085501200", "06085503601", "06085503210", "06085505100"}


def by_rate(pop, rate, lo, hi):
    x = pop * rate / 1000
    n = int(x) + (rng.random() < x - int(x))
    return max(lo, min(hi, n))


for i, t in enumerate(order):
    r = tiers.loc[t]
    if t in ZERO_USUAL:
        n = 0
    elif t in ONE_USUAL:
        n = 0 if r.n_res >= 1 else 1
    elif i < 58:
        n = by_rate(r["pop"], 0.48, 1, 4)
    else:
        n = by_rate(r["pop"], 0.27 if r.priv > 0 else 0.2, 1, 3)
        n = max(0, n - int(r.n_res))
        if r.n_res == 0:
            n = max(1, n)
    alloc[t] = int(n)
for t in sorted(B_TIER):
    r = tiers.loc[t]
    if t in ONE_USUAL:
        alloc[t] = 0 if r.n_res >= 1 else 1
    elif t in ZERO_USUAL or r.n_res >= 1 or r.p311 >= 80:
        alloc[t] = 0
    else:
        alloc[t] = int(r["pop"] >= 3500 and rng.random() < 0.6)
for t in sorted(C_TIER):
    alloc[t] = 0

# ------------------------------------------------------------------ names
FIRST = {"en": ["Margaret", "Daniel", "Priya", "Kevin", "Laura", "Brian", "Megan", "Steven", "Anjali", "Robert", "Heather", "Gregory",
                "Nicole", "Thomas", "Rachel", "Patrick", "Allison", "Jeffrey", "Kristen", "Douglas", "Shreya", "Eric", "Wendy", "Colin",
                "Natalie", "Raj", "Melissa", "Andrew", "Jasmine", "Victor", "Dana", "Trevor", "Leah", "Howard", "Monica", "Ian", "Paula",
                "Neil", "Sunita", "Craig", "Joanne", "Arjun", "Beth", "Martin", "Ellen", "Sean", "Carol", "Vikram", "Tanya", "Gordon",
                "Hiroshi", "Mei", "Olivia", "Marcus", "Grace", "Ethan", "Fatima", "Omar", "Lorraine", "Desmond"],
         "es": ["María", "José", "Guadalupe", "Juan", "Rosa", "Miguel", "Ana", "Luis", "Carmen", "Jorge", "Leticia", "Ricardo", "Elena",
                "Francisco", "Teresa", "Alejandro", "Marisol", "Ramón", "Yolanda", "Arturo", "Silvia", "Héctor", "Norma", "Javier"],
         "vi": ["Nguyễn Văn", "Trần Thị", "Lê Văn", "Phạm Thị", "Hoàng Minh", "Võ Thị", "Đỗ Quang", "Bùi Thị", "Huỳnh Văn", "Ngô Thị"],
         }
LAST = {"en": ["Hollis", "Brennan", "Kapoor", "Lindgren", "Morrow", "Okafor", "Castellano", "Whitaker", "Iyer", "Sorensen", "Gallagher",
               "Tanaka", "Pruitt", "Delgado", "Ashworth", "Nakamura", "Ferreira", "Holloway", "Venkat", "Mercer", "Quinlan", "Abernathy",
               "Osei", "Kowalski", "Rinaldi", "Sato", "Dunmore", "Chandran", "Halvorsen", "Prescott", "Bhatt", "Langley", "Moreau",
               "Esposito", "Fairbanks", "Yamada", "Nwosu", "Albright", "Calloway", "Desai", "Hartley", "Lin", "Zhou", "Pak", "Cho"],
        "es": ["García", "Hernández", "Martínez", "López", "Ramírez", "Flores", "Gómez", "Cruz", "Morales", "Reyes", "Ortega", "Vargas",
               "Castillo", "Mendoza", "Aguilar", "Rosales", "Salazar", "Navarro", "Cervantes", "Ibarra", "Montoya", "Zavala"],
        "vi": ["Hùng", "Lan", "Phúc", "Hạnh", "Tuấn", "Thảo", "Bảo", "Ngọc", "Dũng", "Mai", "Khánh", "Trang", "Vinh", "Hằng"]}
DOMAINS = ["example.com", "example.net", "mail.example.com", "example.com", "inbox.example.net"]
used_addr = set()


def person(lang):
    for _ in range(100):
        if lang == "vi":
            f, l = rng.choice(FIRST["vi"]), rng.choice(LAST["vi"])
            display = f"{f} {l}"
            local = re.sub(r"[^a-z]", "", strip(l).lower()) + "." + re.sub(r"[^a-z]", "", strip(f.split()[0]).lower())
        else:
            f, l = rng.choice(FIRST[lang if lang in FIRST else "en"]), rng.choice(LAST[lang if lang in LAST else "en"])
            display = f"{f} {l}"
            local = strip(f[0]).lower() + re.sub(r"[^a-z]", "", strip(l).lower()) + rng.choice(["", ".sj", "408", str(rng.randint(10, 99))])
        addr = f"{local}@{rng.choice(DOMAINS)}"
        if addr not in used_addr:
            used_addr.add(addr)
            return display, addr
    raise RuntimeError


def strip(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", s.replace("Đ", "D").replace("đ", "d")) if not unicodedata.combining(c))


def signer(display, lang):
    f, *rest = display.split()
    if lang == "vi":
        return display
    r = rng.random()
    return display if r < 0.6 else f if r < 0.8 else f"{f} {rest[-1][0]}."


# ------------------------------------------------------------------ locations
SUF = {"St": "Street", "Ave": "Avenue", "Rd": "Road", "Dr": "Drive", "Blvd": "Boulevard", "Ln": "Lane", "Ct": "Court", "Pl": "Place",
       "Expy": "Expressway", "Pkwy": "Parkway", "Cir": "Circle"}
DIRW = {"N": "North", "S": "South", "E": "East", "W": "West"}


def pretty_street(n, long_):
    t = n.split()
    if long_:
        if t[0] in DIRW:
            t[0] = DIRW[t[0]]
        if t[-1] in SUF:
            t[-1] = SUF[t[-1]]
    return " ".join(t)


used_pairs = {}
GOOD_SUF = {"St", "Ave", "Rd", "Dr", "Blvd", "Ln", "Ct", "Way", "Pl", "Expy", "Pkwy", "Cir"}


def good_name(n):
    t = n.split()
    return 2 <= len(t) <= 4 and t[-1] in GOOD_SUF and t[0] != "St" and not any(x in ("De", "La", "Del", "Las", "Los", "El") for x in t)



def pick_int(tid, key):
    skip = {tuple(x) for x in OVR.get(key, {}).get("skip_int", [])}
    opts = [o for o in ints.get(tid, {}).get("ints", []) if (o["a"], o["b"]) not in skip
            and good_name(o["a"]) and good_name(o["b"])]
    if not opts:
        return None
    opts.sort(key=lambda o: used_pairs.get((o["a"], o["b"]), 0))
    o = opts[0]
    used_pairs[(o["a"], o["b"])] = used_pairs.get((o["a"], o["b"]), 0) + 1
    lg = rng.random() < 0.5
    a, b = pretty_street(o["a"], lg), pretty_street(o["b"], lg)
    if rng.random() < 0.5:
        a, b = b, a
    return a, b, (o["a"], o["b"])


# ------------------------------------------------------------------ dates
def rand_date(topic):
    if topic in ("datacenter", "datacenter_cond"):
        lo, hi = datetime(2026, 9, 1), datetime(2026, 10, 19)
    elif topic in ("rent_support", "rent_oppose", "fourplex_support", "fourplex_oppose", "blossom", "permit_fees", "safety_cameras"):
        lo, hi = (datetime(2026, 6, 1), datetime(2026, 10, 18)) if rng.random() < 0.8 else (datetime(2025, 7, 1), datetime(2026, 5, 31))
    else:
        lo, hi = datetime(2025, 7, 1), datetime(2026, 10, 20)
    d = lo + timedelta(seconds=rng.randint(0, int((hi - lo).total_seconds())))
    d = d.replace(hour=rng.choice([6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]), minute=rng.randint(0, 59))
    pdt = (datetime(d.year, 3, 8) <= d < datetime(d.year, 11, 1))
    return d.strftime("%a, %-d %b %Y %H:%M ") + ("-0700" if pdt else "-0800"), d


TO = {"council": "City Council <council@sanjoseca.example.gov>", "mayor": "Office of the Mayor <mayoremail@sanjoseca.example.gov>",
      "es": "Concejo Municipal / City Council <council@sanjoseca.example.gov>",
      "vi": "Hội đồng Thành phố / City Council <council@sanjoseca.example.gov>"}


def to_field(lang, district):
    r = rng.random()
    if district and r < 0.55:
        return f"District {district} Council Office <district{district}@sanjoseca.example.gov>"
    if lang in ("es", "vi") and r < 0.8:
        return TO[lang]
    return TO["council"] if r < 0.85 else TO["mayor"]


REASON = {"streetlight": "reports streetlights out, asks repair", "pothole": "reports pothole, asks repair or repaving",
          "drainage": "reports clogged storm drain, asks clearing", "crosswalk": "asks crosswalk and beacon at school",
          "dumping": "reports dumping, asks cleanup and camera", "freeway_air": "asks sound wall and trees",
          "rent_support": "vote position on rent cap", "rent_oppose": "vote position on rent cap",
          "eviction": "asks closing remodel eviction loophole", "fourplex_support": "vote position on fourplex reform",
          "fourplex_oppose": "vote position on fourplex reform", "habitability": "reports habitability failure, asks inspector",
          "blight": "reports blighted property, asks enforcement", "permit_delay": "reports stuck permit, asks faster review",
          "permit_fees": "asks fees tied to more staff", "safety_patrol": "reports break-ins, asks more patrols",
          "safety_cameras": "general opposition to camera expansion", "safety_youth": "asks restoring youth program funding",
          "datacenter": "vote position on data center", "datacenter_cond": "asks recycled-water approval condition",
          "blossom": "vote position on rezoning", "senior": "asks restoring senior center hours", "cost": "general cost-of-living frustration",
          "boards": "asks evening interviews, published applicant pools", "immigrant": "vote position on immigrant resolution",
          "bulky": "asks restoring free bulky-item pickup"}

rows, side = [], []
sys.path.insert(0, str(ROOT / "scripts"))
import classify as CL
SH = [CL._shingles(r["body"]) for r in csv.DictReader(open(ROOT / "data/raw/emails/sanjose_city_emails.csv"))]


def distinct(body, margin=0.55):
    A = CL._shingles(body)
    for B in SH:
        u = len(A | B)
        if u and len(A & B) / u >= margin:
            return False
        small = min(len(A), len(B))
        if small >= 15 and len(A & B) / small >= margin:
            return False
    return True


LAST_TOPIC = [None]
ALT = {"en": ["pothole", "streetlight", "dumping", "safety_patrol", "permit_delay", "habitability", "rent_support", "crosswalk", "blight"],
       "es": ["rent_support", "habitability", "streetlight", "dumping", "pothole", "safety_patrol", "cost"],
       "vi": ["rent_support", "habitability", "streetlight", "dumping", "pothole", "safety_patrol", "cost"]}


def compose_distinct(*a, **k):
    a = list(a)
    for i in range(80):
        if i >= 20 and i % 5 == 0:   # small pool exhausted: switch to a topic with more variety
            a[0] = rng.choice(ALT.get(a[1], ALT["en"]))
        out = compose(*a, **k)
        if distinct(out[0]):
            break
    else:
        print("!! could not make distinct:", out[0][:80].replace("\n", " "))
    SH.append(CL._shingles(out[0]))
    LAST_TOPIC[0] = a[0]
    return out


def compose(topic, lang, loc_sentence=None, sig_extra=None, length="medium", persona="resident", org=None):
    tp = P.T[topic]
    L = lang if lang in tp["issue"] else "en"
    issue = rng.choice(tp["issue"][L])
    stance, ask = rng.choice(tp["ask"][L])
    details = list(tp["detail"].get(L, []))
    rng.shuffle(details)
    nd = {"short": 0, "medium": 1, "long": 2}[length]
    p1 = []
    if loc_sentence and rng.random() < 0.6:
        p1 = [loc_sentence, issue]
    elif loc_sentence:
        p1 = [issue, loc_sentence]
    else:
        p1 = [issue]
    p1 += details[:nd]
    if rng.random() < (0.85 if (length == "short" or L != "en") else 0.5):
        pl = rng.choice(P.PERSONAL[L]).format(Y=rng.randint(3, 40), rel=rng.choice(["wife", "husband", "mother", "neighbor", "son", "partner"]),
                                             rel_es=rng.choice(["esposo", "esposa", "hermana", "mamá"]), n=rng.choice(["second", "third", "fourth"]),
                                             n_es=rng.choice(["segunda", "tercera", "cuarta"]), n_vi=rng.choice(["hai", "ba", "tư"]),
                                             h=rng.choice([1, 2, 3, 4, 5, 6, 11]), job=rng.choice(["nurse", "teacher", "software engineer", "bus driver", "contractor", "small business owner", "pharmacist"]),
                                             job_es=rng.choice(["cocinero", "jardinero", "costurera", "cuidadora", "mecánico"]), k=rng.choice([1, 2, 3, 4]),
                                             YR=rng.choice([1988, 1996, 2001, 2005, 2011, 2014, 2019]), age=rng.choice([72, 78, 81, 86]))
        p1.insert(rng.randint(0, len(p1)), pl)
    if org:
        p1.insert(0, org)
    p2 = [ask]
    if length == "long" and L == "en":
        p2.append(rng.choice(["Thank you for reading this.", "I'm happy to talk to staff about it.", "I hope this gets on someone's list.",
                              "We will keep watching how the council votes.", "This has gone on long enough."]))
    greet = rng.choice(P.GREET[L])
    so = rng.choice(P.SIGNOFF[L])
    body_parts = ([greet] if greet else []) + [" ".join(p1), " ".join(p2)]
    sig = ([so] if so else [])
    body = "\n\n".join(body_parts)
    subj = rng.choice(tp["subj"].get(L) or tp["subj"]["en"])
    lab = {"category": tp["cat"], "subcategory": tp["sub"], "confidence": round(rng.uniform(0.82, 0.95), 2), "evidence_quote": issue,
           "stance": stance, "stance_evidence": ask if stance in ("support", "oppose") else ""}
    act = {"actionable": bool(tp["act"]), "reason": REASON[topic]}
    return body, sig, subj, lab, act, L


def add(display, addr, to, date, subj, body, lab, act, meta, attachment=""):
    rows.append({"from": f"{display} <{addr}>", "to": to, "date": date, "subject": subj, "body": body, "attachment": attachment})
    side.append({"row": len(rows) - 1, **meta, "label": lab, "actionable": act})


def choose_topic(persona, lang, tid):
    d = ui.get(tid, {}).get("district") if tid else None
    if lang in ("es", "vi"):
        tops = [t for t in P.NONEN_TOPICS[lang] if lang in P.T[t]["issue"]]
        return rng.choice(tops)
    if persona == "owner":
        t = rng.choices(P.OWNER_TOPICS, P.OWNER_W)[0]
        if d in (9, 10, 2) and rng.random() < 0.12:
            t = "blossom"
    else:
        t = rng.choices(P.TENANT_TOPICS, P.TENANT_W)[0]
    if t.startswith("datacenter") and d not in (3, 4, 6, None):
        t = "pothole"
    return t


def lang_for(tid, tier):
    lg = ui[tid]["lang"]
    sp, ap = lg.get("spanish", 0) or 0, lg.get("asian_pacific", 0) or 0
    r = rng.random()
    if tier == "A":
        return "es" if r < 0.6 * sp else "vi" if r < 0.6 * sp + 0.3 * ap else "en"
    if tier == "B":
        pes, pvi = min(0.75, sp * 1.6), min(0.6, ap * 1.2)
        tot = pes + pvi
        if tot < 0.6:
            pes, pvi = pes * 0.6 / tot, pvi * 0.6 / tot
        return "es" if r < pes else "vi" if r < pes + pvi else "en"
    return "es" if r < 0.75 * sp else "vi" if r < 0.75 * sp + 0.25 * ap else "en"


# ------------------------------------------------------------------ located emails
slot_n = 0
for tid in sorted(alloc):
    n = alloc[tid]
    tier = "A" if tid in A_TIER else "B" if tid in B_TIER else "C" if tid in C_TIER else "M"
    nbs = pretty_nbs(tid)
    for k in range(n):
        key = f"{tid}#{k}"
        lang = lang_for(tid, tier)
        renter = ui[tid]["renter"]
        persona = "owner" if rng.random() > renter else "tenant"
        if rng.random() < 0.08:
            persona = "business"
        f = OVR.get(key, {}).get("force")
        method = f or ("nb" if nbs and (rng.random() < 0.5 or not ints.get(tid, {}).get("ints")) else "int")
        if tier == "A" and k == 2 and nbs:
            method = f or "nb"
        loc_sentence = sig_extra = None
        Y = rng.choice([4, 6, 8, 11, 15, 19, 23, 30])
        meta = {"key": key, "tract": tid, "tier": tier, "lang": lang, "persona": persona}
        if method == "int":
            pi = pick_int(tid, key)
            if pi is None:
                if nbs:
                    method = "nb"
                else:
                    continue
        if method == "int":
            a, b, raw = pi
            if lang == "en" and persona == "business":
                loc_sentence = rng.choice(P.LOC_INT_OWNER).format(A=a, B=b)
            else:
                pool = P.LOC_INT[lang]
                if lang == "en" and persona == "tenant":
                    pool = [s for s in pool if "homeowner" not in s and "My house" not in s]
                if lang == "en" and persona == "owner":
                    pool = [s for s in pool if "rent an" not in s]
                loc_sentence = rng.choice(pool).format(A=a, B=b, Y=Y)
            meta.update(method="int", pair=list(raw))
        elif method == "nb":
            N = nbs[k % len(nbs)] if tier == "A" else rng.choice(nbs)
            if rng.random() < 0.3:
                sig_extra = P.SIG_NB[lang].format(N=N)
            else:
                pool = P.LOC_NB[lang]
                if persona == "tenant":
                    pool = [s for s in pool if "homeowner" not in s]
                loc_sentence = rng.choice(pool).format(N=N, Y=Y, YR=rng.choice([1994, 2003, 2008, 2012, 2016]))
            meta.update(method="nb", nb=N)
        topic = choose_topic("owner" if persona in ("owner", "business") else "tenant", lang, tid)
        if persona == "business" and topic not in P.T or (persona == "business" and not P.T[topic].get("owner_ok")):
            topic = rng.choice(["permit_delay", "dumping", "safety_patrol", "pothole", "streetlight"])
        length = ("short" if rng.random() < 0.7 else "medium") if tier == "B" else rng.choice(["short", "medium", "medium", "long"])
        if lang != "en" and length == "long":
            length = "medium"
        body, sig, subj, lab, act, L = compose_distinct(topic, lang, loc_sentence, sig_extra, length, persona)
        topic = LAST_TOPIC[0]
        display, addr = person(L)
        tail = sig + [signer(display, L)] + ([sig_extra] if sig_extra else [])
        body = body + "\n\n" + "\n".join(tail)
        date, _ = rand_date(topic)
        att = ""
        if topic in ("pothole", "dumping", "blight", "streetlight") and rng.random() < 0.12:
            att = f"{topic}_{rng.randint(100, 999)}.jpg (photo taken by the sender)"
        meta.update(topic=topic)
        add(display, addr, to_field(L, ui[tid].get("district")), date, subj, body, lab, act, meta, att)

# ------------------------------------------------------------------ ZIP-only (signature) emails from homeowner areas
for z in ["95120", "95118", "95125", "95135", "95138", "95129"]:
    topic = rng.choice(["pothole", "permit_delay", "safety_patrol", "fourplex_oppose", "streetlight"])
    body, sig, subj, lab, act, L = compose_distinct(topic, "en", None, None, "medium", "owner")
    topic = LAST_TOPIC[0]
    display, addr = person("en")
    body += "\n\n" + "\n".join(sig + [display, "San José, CA " + z])
    date, _ = rand_date(topic)
    add(display, addr, to_field("en", None), date, subj, body, lab, act, {"key": f"zip{z}", "method": "zip", "topic": topic, "lang": "en"})

# ------------------------------------------------------------------ organizations (fictional)
ORGS = [("Briarwood Neighborhood Association (fictional)", "board@briarwood-na.example.org", "06085502902", "Briarwood", "pothole"),
        ("Almaden Valley Homeowners Council (fictional)", "info@avhc.example.org", "06085511914", "Guadalupe Oak Grove", "fourplex_oppose"),
        ("Silver Creek Valley Neighbors (fictional)", "contact@scvneighbors.example.org", "06085503339", "Silver Creek", "safety_patrol"),
        ("Willow Glen Business & Residents Alliance (fictional)", "office@wgbra.example.org", None, None, "permit_delay"),
        ("South Bay Renters Union (fictional)", "organize@sbru.example.org", None, None, "eviction"),
        ("Cambrian Park Garden Club (fictional)", "garden@cpgc.example.org", "06085502701", "Cambrian Park", "drainage"),
        ("Evergreen Families for Safe Streets (fictional)", "hello@effss.example.org", None, None, "crosswalk"),
        ("Asociación de Inquilinos del Este (fictional)", "info@aie-sj.example.org", None, None, "habitability")]
for name, addr, tid, nb, topic in ORGS:
    lang = "es" if "Asociación" in name else "en"
    org_line = None
    if nb:
        org_line = f"Our association represents about {rng.choice([300, 420, 650, 900])} households in {nb}." if lang == "en" else None
    else:
        org_line = "We are writing on behalf of our members." if lang == "en" else "Escribimos en nombre de nuestros miembros."
    body, sig, subj, lab, act, L = compose_distinct(topic, lang, None, None, "long" if lang == "en" else "medium", "owner", org=org_line)
    topic = LAST_TOPIC[0]
    fn, ln = rng.choice(FIRST["en"]), rng.choice(LAST["en"])
    body += "\n\n" + "\n".join((sig or ["Sincerely,"]) + [f"{fn} {ln}", rng.choice(["Board President", "Chair", "Coordinator", "Secretary"])])
    date, _ = rand_date(topic)
    add(name, addr, to_field(L, ui[tid]["district"] if tid else None), date, subj, body, lab, act,
        {"key": "org:" + name, "method": "nb" if nb else "none", "tract": tid, "nb": nb, "topic": topic, "lang": lang, "persona": "org"})

# ------------------------------------------------------------------ form-letter campaign (bulky-item pickup)
CAMP = ("Please restore the free bulky-item pickup appointments that were cut this year. Since the change, mattresses, couches and "
        "appliances end up on sidewalks and in creeks instead of at the curb on a scheduled day. Prevention costs less than "
        "cleanup. I SUPPORT funding free bulky-item pickup and neighborhood dump days.")
CAMP_LINES = ["Our street has had three couches dumped since spring.", "", "I used to book one every year.", "My elderly neighbor has no truck."]
for i, extra in enumerate(CAMP_LINES):
    display, addr = person("en")
    body = ("Dear Council,\n\n" if i % 2 == 0 else "Hello Councilmembers,\n\n") + CAMP + ("\n\n" + extra if extra else "") + "\n\n" + display
    date = (datetime(2026, 8, 18, 9, 0) + timedelta(hours=7 * i)).strftime("%a, %-d %b %Y %H:%M -0700")
    lab = {"category": "sanitation_environment_quality", "subcategory": "dumping_prevention_access", "confidence": 0.93,
           "evidence_quote": "Please restore the free bulky-item pickup appointments that were cut this year.", "stance": "support",
           "stance_evidence": "I SUPPORT funding free bulky-item pickup and neighborhood dump days."}
    add(display, addr, TO["council"], date, "Restore free bulky-item pickup", body, lab, {"actionable": True, "reason": REASON["bulky"]},
        {"key": f"camp{i}", "method": "none", "topic": "bulky", "lang": "en"})

# ------------------------------------------------------------------ Chinese and Tagalog (hand-written)
HAND = [
    ("zh", "陈美玲", "Chen.meiling@example.com", "社区街灯问题",
     "尊敬的市议会：\n\n我们街区的路灯已经坏了一个多月，晚上非常黑，老人不敢出门散步。我已经在网上报修两次，但一直没有人来修理。\n\n请尽快派人修好路灯。谢谢！\n\n陈美玲",
     ("infrastructure_streets", "streetlight_outage", "我们街区的路灯已经坏了一个多月，晚上非常黑，老人不敢出门散步。", "support", "请尽快派人修好路灯。"), True, "streetlight"),
    ("zh", "王建国", "wang.jianguo@example.net", "小餐馆许可证拖延",
     "您好：\n\n我在申请开一家小餐馆，许可证审批已经等了八个月，每次都要求补交新的文件。每个月我都要付空店面的租金。\n\n希望市政府加快许可证审批，增加审图人员。\n\n王建国",
     ("code_enforcement_habitability", "permit_backlog_delays", "许可证审批已经等了八个月，每次都要求补交新的文件。", "support", "希望市政府加快许可证审批，增加审图人员。"), True, "permit_delay"),
    ("zh", "李淑芬", "lishufen88@example.com", "老人中心开放时间",
     "市议员您好：\n\n老人活动中心把开放时间减少到每周三天，我母亲现在大部分时间一个人在家吃午饭，很孤单。\n\n请恢复原来的开放时间。谢谢。",
     ("other", "senior_services_general", "老人活动中心把开放时间减少到每周三天，我母亲现在大部分时间一个人在家吃午饭，很孤单。", "support", "请恢复原来的开放时间。"), True, "senior"),
    ("zh", "张伟", "zhangwei.sj@example.net", "房租太高",
     "议员们好，\n\n我们家租房住，每年房租都涨，现在房租已经占了一半的收入。请支持降低每年房租上涨的上限 (rent cap)。\n\n张伟",
     ("housing_affordability_policy", "rent_stabilization", "我们家租房住，每年房租都涨，现在房租已经占了一半的收入。", "support", "请支持降低每年房租上涨的上限 (rent cap)。"), False, "rent_support"),
    ("tl", "Maricel Dizon", "mdizon@example.com", "Walang mainit na tubig sa apartment",
     "Magandang araw po,\n\nIsang linggo na po kaming walang mainit na tubig sa aming apartment at hindi sumasagot ang may-ari. Ang mga anak ko ay naliligo sa malamig na tubig.\n\nSana po ay magpadala kayo ng inspector sa lalong madaling panahon. Salamat po.\n\nMaricel Dizon",
     ("code_enforcement_habitability", "habitability_hot_water_mold", "Isang linggo na po kaming walang mainit na tubig sa aming apartment at hindi sumasagot ang may-ari.", "support", "Sana po ay magpadala kayo ng inspector sa lalong madaling panahon."), True, "habitability"),
    ("tl", "Rodel Bautista", "rbautista.sj@example.net", "Madilim ang kalye namin",
     "Mahal na Konseho,\n\nIlang linggo na pong patay ang mga ilaw sa kalye namin. Natatakot ang mga kapitbahay na maglakad sa gabi.\n\nPakiayos po agad. Salamat.\n\nRodel Bautista",
     ("infrastructure_streets", "streetlight_outage", "Ilang linggo na pong patay ang mga ilaw sa kalye namin.", "support", "Pakiayos po agad."), True, "streetlight"),
    ("tl", "Lorna Villanueva", "lvillanueva@example.com", "Mahal ng upa",
     "Magandang gabi po,\n\nTaon-taon pong tumataas ang upa namin at halos kalahati na ng sahod ko ang napupunta dito. Hirap na hirap na po ang pamilya namin.\n\nSalamat po sa pakikinig.\n\nLorna Villanueva",
     ("other", "personal_financial_hardship", "Taon-taon pong tumataas ang upa namin at halos kalahati na ng sahod ko ang napupunta dito.", "unclear", ""), False, "cost"),
]
for lang, display, addr, subj, body, (cat, sub, eq, st, se), actv, topic in HAND:
    date, _ = rand_date(topic)
    add(display, addr.lower(), TO["council"], date, subj, body,
        {"category": cat, "subcategory": sub, "confidence": 0.9, "evidence_quote": eq, "stance": st, "stance_evidence": se},
        {"actionable": actv, "reason": REASON[topic]}, {"key": "hand:" + display, "method": "none", "topic": topic, "lang": lang})

# ------------------------------------------------------------------ unlocated (and a few district-only) emails
n_loc = len(rows)
target_total = int(round(n_loc / 0.715))
k = 0
while len(rows) < target_total:
    r = rng.random()
    lang = "es" if r < 0.24 else "vi" if r < 0.34 else "en"
    persona = "owner" if rng.random() < 0.5 else "tenant"
    topic = choose_topic(persona, lang, None)
    if topic == "blossom" and rng.random() < 0.5:
        topic = "pothole"
    org = None
    if k % 25 == 3 and lang == "en":
        org = f"I'm a District {rng.choice([1, 9, 10, 8, 6])} resident."
    body, sig, subj, lab, act, L = compose_distinct(topic, lang, None, None, rng.choice(["short", "short", "medium", "long"]) if lang == "en" else
                                           rng.choice(["short", "medium"]), persona, org=org)
    topic = LAST_TOPIC[0]
    display, addr = person(L)
    body += "\n\n" + "\n".join(sig + [signer(display, L)])
    date, _ = rand_date(topic)
    add(display, addr, to_field(L, None), date, subj, body, lab, act,
        {"key": f"none{k}", "method": "district" if org else "none", "topic": topic, "lang": L})
    k += 1

# sort by date like an inbox export
def _dt(s):
    from email.utils import parsedate_to_datetime
    return parsedate_to_datetime(s["date"])

idx = sorted(range(len(rows)), key=lambda i: _dt(rows[i]))
rows2 = [rows[i] for i in idx]
side2 = []
for new, i in enumerate(idx):
    s = dict(side[i]); s["row"] = new; side2.append(s)
OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["from", "to", "date", "subject", "body", "attachment"])
    w.writeheader()
    w.writerows(rows2)
(SCR / "side.json").write_text(json.dumps(side2, ensure_ascii=False, indent=1))
from collections import Counter
print(len(rows2), "emails;", Counter(s.get("method") for s in side2), Counter(s.get("lang") for s in side2))
print("tiers", Counter(s.get("tier") for s in side2 if s.get("tier")), "located tracts", len({s["tract"] for s in side2 if s.get("tract")}))
