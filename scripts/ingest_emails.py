#!/usr/bin/env python3
"""Step b: the simulated email channel, from the user-supplied CSV. No emails are generated here.

Input : data/raw/emails/sanjose_city_emails.csv (gitignored; columns from, to, date, subject, body, attachment)
        data/raw/emails/sanjose_city_emails_generated.csv (optional, gitignored; same columns). Written by the build
                 agent to widen geographic coverage; its rows carry generated=true, generated_by="build agent" and
                 source_file so they stay distinguishable from the user-supplied emails everywhere downstream.
Output: data/emails_raw.csv                   voice rows, PII-free, channel=email, mock=true
        public/data/inbox.json                emails "as received" for the Inbox panel (names/addresses removed)
        public/data/fixtures/emails.json      committed copy for offline runs
        data/raw/emails/location_hints.json   gitignored (same shape as the letters' hints file)

The CSV has no agenda items, so each email is assigned to a simulated agenda item by topic rules below
(MOCK_ITEMS). Both the emails and those items are labeled simulated everywhere.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from email.utils import parsedate_to_datetime, parseaddr
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "emails" / "sanjose_city_emails.csv"
SRC_GENERATED = ROOT / "data" / "raw" / "emails" / "sanjose_city_emails_generated.csv"
GENERATED_BY = "build agent"
CSV_OUT = ROOT / "data" / "emails_raw.csv"
INBOX = ROOT / "public" / "data" / "inbox.json"
FIXTURE = ROOT / "public" / "data" / "fixtures" / "emails.json"
HINTS = ROOT / "data" / "raw" / "emails" / "location_hints.json"

# Simulated agenda items (fictional). Each has strong cues (weight 3: name the item) and weak cues (weight 1:
# thread context). Highest score wins; ties go to the earlier entry; no hit -> general correspondence.
MOCK_ITEMS = [
    ("MOCK-26-910", "Rezoning application: Blossom Hill Road retail parcel", "2026-10-06", r"blossom hill", r"strip mall"),
    ("MOCK-26-901", "Terra Verde data center: EIR certification and site development permit", "2026-10-20",
     r"terra verde|data cent|centro de datos|trung tâm dữ liệu", r"alviso|cooling"),
    ("MOCK-26-905", "Citywide fourplex zoning reform", "2026-09-22",
     r"fourplexes|fourplex reform|upzon|single-family|más (?:unidades|vivienda)", r"more homes|density|phase it in|need housing|four units|historic (?:neighborhoods|districts)|infrastructure plan"),
    ("MOCK-26-902", "Streetlight reliability program and maintenance contract (Story/King corridor)", "2026-09-15",
     r"streetlight|street light|luces|đèn đường|light towers|portable lights|lights (?:are|went) (?:off|out)|outage",
     r"\blights\b|\bdark\b|oscur|that corridor|fund a program|copper"),
    ("MOCK-26-903", "Pavement maintenance: emergency repair on Alma Avenue and road funding", "2026-09-29",
     r"pothole|alma ave|bache", r"road-repair|repave|crater"),
    ("MOCK-26-904", "Proactive rental inspection and habitability enforcement", "2026-10-13",
     r"cedar court|hot water|agua caliente|nước nóng|habitability|rental inspection", r"proactive|inspection|cold water|boiler|slumlord|retaliat"),
    ("MOCK-26-906", "Apartment Rent Ordinance amendment: annual rent-increase cap", "2026-09-29",
     r"rent cap|rent control|rent ordinance|rent-increase|rent stabilization|lower(?:ing)? the (?:annual )?cap|tiền thuê|renta\b",
     r"\bcap\b|my rent|rent is insane|landlord"),
    ("MOCK-26-907", "Illegal dumping response and Coyote Creek cleanup", "2026-09-22", r"dump|coyote creek|basura", r"creek|bulky"),
    ("MOCK-26-908", "Permitting modernization and fee schedule", "2026-09-29", r"permit|permisos", r"plan checkers"),
    ("MOCK-26-909", "Public safety budget: patrols, community service officers, cameras", "2026-09-15",
     r"break-ins|police|catalytic|surveillance|robos|community service officers", r"crime|patrol|youth programs"),
]
GENERAL = ("MOCK-GEN", "General correspondence (no agenda item)", "")


def assign_item(to: str, subject: str, body: str) -> tuple[str, str, str]:
    hay = f"{to}\n{subject}\n{body}".lower()
    best, best_score = None, 0
    for item_id, title, date, strong, weak in MOCK_ITEMS:
        score = 3 * len(re.findall(strong, hay, re.I)) + len(re.findall(weak, hay, re.I))
        if score > best_score:
            best, best_score = (item_id, title, date), score
    return best or GENERAL


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
STREET_RE = re.compile(r"\b\d{1,5}\s+(?:[NSEW]\.?\s+)?[A-Z][A-Za-z0-9'.-]*(?:\s+[A-Z][A-Za-z0-9'.-]*){0,3}\s+"
                       r"(?:St|Street|Ave|Avenue|Blvd|Rd|Road|Dr|Drive|Way|Ct|Court|Ln|Lane|Pl)\b\.?")
ZIP_RE = re.compile(r"\b(95\d{3})\b")
TITLE_RE = re.compile(r"^(?:Dr|Mr|Mrs|Ms|Rev|Councilwatch)\.?\s+", re.I)


def name_tokens(display: str) -> list[str]:
    display = re.sub(r"\(fictional\)", "", display, flags=re.I)
    display = TITLE_RE.sub("", display).strip()
    toks = [t.strip(".,") for t in re.split(r"\s+", display) if len(t.strip(".,")) >= 2]
    stop = {"the", "of", "and", "city", "council", "group", "email", "rep", "mgmt", "property", "small", "landlord",
            "anonymous", "contractor", "no", "name", "given", "iii", "phd", "assoc"}
    return [t for t in toks if t.lower() not in stop]


SIGNOFF_RE = re.compile(r"^(?:respectfully|sincerely|regards|best|thanks|thank you(?: for .*)?|cheers|atentamente|gracias|"
                        r"saludos|trân trọng|cảm ơn.*|xin cảm ơn.*|with appreciation|warmly)[,.!]?$", re.I)
TITLE_WORDS = re.compile(r"\b(director|chair|coordinator|president|executive|manager|affairs|board|secretary|"
                         r"treasurer|organizer|pastor|reverend|founder|member|resident|tenant|owner)\b", re.I)
PERSON_LINE = re.compile(r"^(?:(?:Dr|Mr|Mrs|Ms|Rev)\.?\s+)?[A-ZÀ-Ỹ][\w'À-ỹ.-]*(?:\s+[A-ZÀ-Ỹ][\w'À-ỹ.-]*){0,3}\.?$")


def scrub_signoff(text: str) -> str:
    lines = text.split("\n")
    for i, l in enumerate(lines):
        if SIGNOFF_RE.match(l.strip()):
            for j in range(i + 1, min(i + 3, len(lines))):
                c = lines[j].strip()
                if c and PERSON_LINE.match(c) and not TITLE_WORDS.search(c):
                    lines[j] = "[name removed]"
    return "\n".join(lines)


def scrub(text: str, display: str, local_part: str, signature: bool = True) -> str:
    text = EMAIL_RE.sub("[email removed]", text)
    text = PHONE_RE.sub("[phone removed]", text)
    toks = name_tokens(display)
    if len(toks) >= 2:
        text = re.sub(r"\b" + r"\s+".join(re.escape(t) for t in toks) + r"\b\.?", "[name removed]", text, flags=re.I)
    # signature lines: last 4 lines that contain any sender-name token (or an initial form like "Carla B.")
    if not signature:
        return text.strip()
    text = scrub_signoff(text)
    lines = text.split("\n")
    for i in range(max(0, len(lines) - 4), len(lines)):
        l = lines[i].strip()
        if not l or len(l) > 60:
            continue
        if any(re.search(r"\b" + re.escape(t) + r"\b", l, re.I) for t in toks if len(t) >= 3) or \
                (local_part and re.fullmatch(r"[A-Z][a-z]+(?: [A-Z]\.?)?", l) and l.split()[0].lower() in local_part.lower()):
            lines[i] = "[name removed]"
    return "\n".join(lines).strip()


def commenter_type(display: str, addr: str, body: str) -> str:
    dom = addr.split("@")[-1].lower()
    if re.search(r"property mgmt|management", display, re.I):
        return "developer_or_counsel"
    if dom.endswith(".org") or "(fictional)" in display or re.search(r"group email|on behalf of", f"{display} {body[:400]}", re.I):
        return "organization"
    return "resident"


def detect_lang(text: str) -> str:
    try:
        from langdetect import DetectorFactory, detect
        DetectorFactory.seed = 0
        return detect(text[:2000])
    except Exception:
        return "en"


def parse_attachment(s: str) -> list[dict]:
    if not s.strip():
        return []
    m = re.match(r"\s*([^\s—]+\.\w{3,4})\s*(?:—\s*(\S+)|\((.*)\))?", s)
    if not m:
        return [{"file": s[:80], "kind": "other", "served": False}]
    file = m.group(1)
    kind = "image" if re.search(r"\.(jpe?g|png|gif)$", file, re.I) else "pdf" if file.lower().endswith(".pdf") else "other"
    return [{"file": file, "kind": kind, "description": (m.group(3) or "").strip(),
             "source_url_raw_only": bool(m.group(2)), "redacted": False, "served": False}]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="use the committed fixture (no raw CSV needed)")
    args = ap.parse_args(argv)
    log = lambda s: print(s, file=sys.stderr, flush=True)
    if args.offline or not SRC.exists():
        payload = json.loads(FIXTURE.read_text())
        rows = payload["rows"]
        pd.DataFrame(rows).drop(columns=["attachments"], errors="ignore").to_csv(CSV_OUT, index=False)
        INBOX.write_text(json.dumps(payload["inbox"], ensure_ascii=False, indent=1))
        log(f"[offline] {len(rows)} simulated emails from fixture")
        return 0

    frames = []
    for path, generated in ((SRC, False), (SRC_GENERATED, True)):
        if path.exists():
            f = pd.read_csv(path, dtype=str).fillna("")
            f["_source_file"], f["_generated"], f["_source_row"] = path.name, generated, range(len(f))
            frames.append(f)
    df = pd.concat(frames, ignore_index=True)
    rows, inbox, hints, first_by_identity = [], [], {}, {}
    for i, r in df.iterrows():
        display, addr = parseaddr(r["from"])
        display = display or addr.split("@")[0]
        via = "ecomments_portal" if "ecomments portal" in r["to"].lower() else "email"
        item_id, item_title, meeting_date = assign_item(r["to"], r["subject"], r["body"])
        if via == "ecomments_portal":  # the portal names the item explicitly; use it when it maps
            hit = assign_item("", r["to"], "")
            if hit[0] != "MOCK-GEN":
                item_id, item_title, meeting_date = hit
        is_org = "(fictional)" in display or addr.lower().endswith(".org")
        # an organization's name is not personal data; its human signer is (handled by the sign-off scrub)
        text = scrub(r["body"], "" if is_org else display, addr.split("@")[0])
        subject = scrub(r["subject"], "" if is_org else display, "", signature=False)
        try:
            received = parsedate_to_datetime(r["date"]).isoformat()
        except Exception:
            received = ""
        ident = "sha256:" + hashlib.sha256(addr.lower().encode()).hexdigest()[:16]
        cid = "E" + hashlib.sha1((item_id + text).encode("utf-8")).hexdigest()[:8]
        to_office = re.sub(r"\s*<[^>]*>", "", r["to"]).strip()
        atts = parse_attachment(r["attachment"])
        rows.append({
            "comment_id": cid, "item": item_id, "item_id": item_id, "item_title": item_title, "meeting_id": "",
            "meeting_date": meeting_date, "channel": "email", "mock": True, "submitted_via": via, "to_office": to_office,
            "received_at": received, "posted_raw": r["date"], "after_deadline": None, "stance": "unclear",
            "stance_source": "pending_llm", "neighborhood": "", "zip": "", "text": text, "source_url": "",
            "subject": subject, "language": detect_lang(r["body"]),
            "commenter_type": commenter_type(display, addr, r["body"]), "identity_hash": ident, "duplicate_of": None,
            "ocr": False, "has_address_hint": False, "attachments": atts, "row_index": int(i),
            "source_file": r["_source_file"], "source_row": int(r["_source_row"]), "generated": bool(r["_generated"]),
            "generated_by": GENERATED_BY if r["_generated"] else ""})
        sig = "\n".join(r["body"].split("\n")[-6:])
        m, z = STREET_RE.search(sig), ZIP_RE.search(sig)
        if m or z:
            hints[cid] = {"address": m.group(0) if m else "", "cross_street": "", "zip": z.group(1) if z else ""}
            rows[-1]["has_address_hint"] = bool(m)
            rows[-1]["zip"] = z.group(1) if z else ""

    # cross-channel duplicates: a portal resubmission by the same sender points at their email
    by_ident: dict[str, list[dict]] = {}
    for row in rows:
        by_ident.setdefault(row["identity_hash"], []).append(row)
    for group in by_ident.values():
        emails = [g for g in group if g["submitted_via"] == "email"]
        for g in group:
            if g["submitted_via"] == "ecomments_portal" and emails:
                same_item = [e for e in emails if e["item"] == g["item"]] or emails
                g["duplicate_of"] = same_item[0]["comment_id"]
    # exact-text repeats within an item get suffixed ids, as for letters
    seen: dict[str, int] = {}
    for row in rows:
        n = seen.get(row["comment_id"], 0)
        seen[row["comment_id"]] = n + 1
        if n:
            row["duplicate_of"] = row["duplicate_of"] or row["comment_id"]
            row["comment_id"] = f"{row['comment_id']}-{n + 1}"

    for row in rows:
        inbox.append({"comment_id": row["comment_id"], "mock": True, "received_at": row["received_at"],
                      "from": "[name and address removed at ingest]", "to": row["to_office"], "subject": row["subject"],
                      "body": row["text"], "language": row["language"], "submitted_via": row["submitted_via"],
                      "item": row["item"], "item_title": row["item_title"], "attachments": row["attachments"],
                      "generated": row["generated"], "generated_by": row["generated_by"], "source_file": row["source_file"]})
    inbox.sort(key=lambda x: x["received_at"], reverse=True)

    out = pd.DataFrame(rows).drop(columns=["attachments", "row_index"])
    out.to_csv(CSV_OUT, index=False, quoting=csv.QUOTE_MINIMAL)
    n_gen = sum(1 for r in rows if r["generated"])
    source = "user-supplied simulated emails (sanjose_city_emails.csv)"
    if n_gen:
        source += f" + {n_gen} simulated emails generated by the build agent (sanjose_city_emails_generated.csv; generated=true)"
    INBOX.write_text(json.dumps({"mock": True, "source": source, "emails": inbox},
                                ensure_ascii=False, indent=1))
    HINTS.parent.mkdir(parents=True, exist_ok=True)
    HINTS.write_text(json.dumps(hints, indent=1))
    FIXTURE.write_text(json.dumps({"rows": [{k: v for k, v in r.items() if k != "row_index"} for r in rows],
                                   "inbox": json.loads(INBOX.read_text())}, ensure_ascii=False, indent=1))
    items = out.groupby(["item", "item_title"]).size().sort_values(ascending=False)
    log(f"{len(out)} simulated emails -> {CSV_OUT.relative_to(ROOT)}; portal duplicates={int(out['duplicate_of'].notna().sum())}; "
        f"languages={out['language'].value_counts().to_dict()}; types={out['commenter_type'].value_counts().to_dict()}; "
        f"generated by build agent={int(out['generated'].sum())}")
    for (k, t), n in items.items():
        log(f"  {n:3d}  {k}  {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
