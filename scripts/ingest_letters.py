#!/usr/bin/env python3
"""Step a2: ingest local "Letters from the Public" PDFs -> one PII-free comment row per letter.

Input : data/raw/legistar/<matter_file>/*.pdf  (all of a matter's PDFs are processed together)
        data/raw/legistar/items.csv  (sidecar: matter_file, title, meeting_date, body, legistar_url, agenda_number,
                                      comment_deadline[optional ISO datetime, filled in by staff])
        data/legistar_items.json     (optional enrichment from ingest_legistar.py: matter_id, event_id, attachment urls)
Output: data/comments_raw.csv, public/data/comments_raw.json, public/data/fixtures/letters.json  (all PII-free)
        data/raw/legistar/location_hints.json  (gitignored; raw signature-block addresses for geocoding)

No crawling here: `--crawl` is a stub; scripts/ingest_legistar.py inventories/downloads via the Legistar Web API.

Text extraction: pdfplumber; a page with < 50 characters is OCR'd with pytesseract (ocr=true) when tesseract is
installed, otherwise tagged ocr_missing. Page text is cached in data/raw/legistar/textcache/.

Splitting. The Clerk's bundles are Outlook forwards: each email starts on a page carrying the Outlook logo line
("Outlook", OCR'd as e.g. "Ga Outlook") followed by the forward header and the inner From:/Sent:/To:/Subject: block
of the original sender. Each such page starts a *unit*; bundles without that wrapper are split on inner header
blocks instead. A unit is a **letter** if an inner From:+Subject: (or From:+Sent:) block appears within its first
40 non-empty lines (or the Outlook header itself names a non-City sender, i.e. a direct send); otherwise it is an
**exhibit** and is attached to the preceding letter. Inside a letter, pages after the end of the email body (the
City's "This message is from outside the City email system" footer, an EXHIBIT/ATTACHMENT page, or the sign-off
when the email lists attachments) are exhibit pages. Exhibits are never comment rows.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from collections import Counter
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "legistar"
ITEMS_CSV = RAW_DIR / "items.csv"
ITEMS_JSON = ROOT / "data" / "legistar_items.json"
CSV_OUT = ROOT / "data" / "comments_raw.csv"
JSON_OUT = ROOT / "public" / "data" / "comments_raw.json"
FIXTURE = ROOT / "public" / "data" / "fixtures" / "letters.json"
HINTS_OUT = RAW_DIR / "location_hints.json"
TZ = ZoneInfo("America/Los_Angeles")
MIN_CHARS = 50
MAX_BODY = 8000
LETTER_HEADER_WINDOW = 40
SHORT_BODY = 200  # below this, the first exhibit pages' text is appended so "see attached" letters keep substance
CRAWL_MSG = "crawl not implemented tonight; run scripts/ingest_legistar.py to inventory/download via the Legistar Web API"
COMMENTER_TYPES = ["resident", "organization", "developer_or_counsel", "government"]

FIELDS = ["comment_id", "item", "item_id", "item_title", "meeting_id", "meeting_date", "channel", "mock",
          "received_at", "posted_raw", "after_deadline", "stance", "stance_source", "neighborhood", "zip", "text",
          "source_url", "subject", "language", "commenter_type", "identity_hash", "duplicate_of", "ocr",
          "has_address_hint", "pdf_file", "pdf_page_start", "pdf_page_end", "pages_total", "pages_exhibit"]

HDR_FROM = re.compile(r"^\W{0,2}\s*F?rom:\s*(.*)$", re.I)  # OCR sometimes drops the F
HDR_SENT = re.compile(r"^\W{0,2}\s*(Sent|Date):\s*(.*)$", re.I)
HDR_SUBJ = re.compile(r"^\W{0,2}\s*Subject:\s*(.*)$", re.I)
HDR_SENT_ONLY = re.compile(r"^\W{0,2}\s*Sent:", re.I)
HDR_FOLLOW = re.compile(r"^\W{0,2}\s*(Sent|Date|Subject):", re.I)
HDR_LINE = re.compile(r"^\W{0,2}\s*(From|Sent|Date|To|Cc|Ce|Bcc|Subject|Importance|Attachments?):", re.I)
# Outlook-web print header (no colons): "From City Clerk <...>", "Date Mon 1/13/2025 8:13 AM", "To ...", "Cc ..."
OUT_FROM = re.compile(r"^\s*Fro\w{0,2}\s+(?!:)(\S.*)$")
OUT_LINE = re.compile(r"^\s*(Fro\w{0,2}|Date|To|Cc|Ce|Bcc)\s+(?!:)\S")
OUT_DATE = re.compile(r"^\s*Date\s+(\S.*)$")
LOGO_RE = re.compile(r"^(?:\S{1,3}\s+){0,2}Outlook\s*$")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
ZIP_RE = re.compile(r"\b(95\d{3})(?:-\d{4})?\b")
STREET_SUFFIX = (r"St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Way|Ct|Court|Ln|Lane|Pl|Place|Cir|Circle|"
                 r"Ter|Terrace|Expy|Expressway|Hwy|Pkwy")
STREET_RE = re.compile(
    r"\b\d{1,5}\s+(?:[NSEW]\.?\s+)?[A-Z][A-Za-z0-9'.-]*(?:\s+[A-Z][A-Za-z0-9'.-]*){0,3}\s+(?:" + STREET_SUFFIX + r")\b\.?",
    re.I)
CROSS_RE = re.compile(r"\b(?:corner of|intersection of|at)\s+([A-Z][\w.']*(?:\s+(?:St|Street|Ave|Avenue|Blvd|Rd|Road|Dr|Way|Expy))?)\s+(?:and|&|/)\s+([A-Z][\w.']*(?:\s+(?:St|Street|Ave|Avenue|Blvd|Rd|Road|Dr|Way|Expy))?)\b")
PERSONAL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com", "me.com",
                    "comcast.net", "att.net", "sbcglobal.net", "live.com", "msn.com", "protonmail.com", "pm.me",
                    "ymail.com", "mac.com", "googlemail.com", "earthlink.net", "verizon.net", "proton.me"}
# bulk-advocacy send platforms: the domain says nothing about the sender (template campaign letters)
ADVOCACY_PLATFORMS = ("actionnetwork.org", "everyaction.com", "ngpvan.com", "votervoice.net", "phone2action.com",
                      "p2a.co", "quorum.us", "newmode.net", "oneclickpolitics.com", "actionkit.com", "salsalabs.net")
# City of San José staff / inboxes that forward letters (never the commenter)
FORWARDER = re.compile(r"City Cl[ae]rk|Agenda ?desk|Rules and Open Gov|Rules Committee|Office of (?:the )?Mayor|"
                       r"sanjoseca\.gov|^\s*District ?\d|PSFSS ?committee|\(CMO\)|Jones, Michael", re.I)
WRAPPER_NOISE = re.compile(r"^(\W{0,3}\w{0,3}\s*Outlook|®|\W{0,2}\s*U?\s*\d+ attachments? \(.*\)|.*\.(pdf|docx?|jpe?g|png);?\s*|"
                           r"\d{1,4}/?\d{1,2}/?\d{2,4},? .*Out\w{0,3}k|.*Committee Agendas?\s*-\s*Out\w*|"
                           r".*\bout\w{0,3}k\s*\.?\s*of+ice\s*3\d5.*|.*office ?3\d5\s*\.\s*co.*|.*\.\.\.?\s*\d/\d)$", re.I)
# a second email's header inside a unit whose Outlook logo was lost to OCR, or a quoted reply
INNER_CUT = re.compile(r"^\s*(Date\s+\w{3}\s+\d{1,2}/\d{1,2}/\d{4}|On .{6,80}\b(wrote:|\d{1,2}:\d{2}\s*[AP]M,?.*)$|-+\s*Original Message\s*-+)", re.I)
BOILERPLATE = re.compile(
    r"External Email\.? Do not open links|You don'?t often get email|Some people who received this message|"
    r"Learn why this is imp|Learn morel?\b|aka\.ms/LearnAboutSender|often get email|carn why this is imp|"
    r"^\s*Caution:.*external|Sent from my (iPhone|iPad|Galaxy|Android)|Get Outlook for|"
    r"This message is from outside the City email system", re.I)
FOOTER = re.compile(r"This message is from outside the City email system", re.I)
EXHIBIT_PAGE = re.compile(r"^\s*(EXHIBIT|ATTACHMENT|Attachment [A-Z0-9]|Exhibit [A-Z0-9])", re.I)
ATTACH_HDR = re.compile(r"^\W{0,2}\s*(Attachments?:|U?\s*\d+ attachments? \()", re.I | re.M)
SIGNOFF = re.compile(r"^\s*(Sincerely|Respectfully|Regards|Best regards|Kind regards|Warm regards|Best|Thanks|"
                     r"Thank you|Many thanks|In partnership|In solidarity|With gratitude|Cordially|Yours truly)\b.{0,25}$",
                     re.I)
NEIGHBORHOODS = ["Alum Rock", "Almaden", "Berryessa", "Blossom Valley", "Cambrian", "Communications Hill", "Downtown",
                 "East San Jose", "East Side", "Edenvale", "Evergreen", "Japantown", "Mayfair", "Naglee Park", "North San Jose",
                 "Rose Garden", "Santa Teresa", "Seven Trees", "Silver Creek", "Spartan Keyes", "Tully", "Willow Glen",
                 "Winchester", "Alviso", "Little Saigon", "Little Portugal", "Story Road", "King Road", "Monterey Road",
                 "Coyote Valley", "Hensley", "Vendome", "Buena Vista", "Burbank", "Shasta Hanchett", "College Park", "Roosevelt Park",
                 "Luna Park", "Northside", "Washington", "Gardner", "Tamien", "Calabazas", "Lynbrook", "West San Jose", "Cupertino"]
NEIGH_RE = re.compile(r"\b(" + "|".join(re.escape(n) for n in NEIGHBORHOODS) + r")\b", re.I)
STREETS = ["Story", "King", "Tully", "Alum Rock", "Monterey", "Senter", "Capitol", "Santa Clara", "First", "Market",
           "Almaden", "Blossom Hill", "Hillsdale", "Saratoga", "Stevens Creek", "Winchester", "Bascom", "Meridian",
           "Camden", "Branham", "Curtner", "Hamilton", "Julian", "Taylor", "Hedding", "Berryessa", "McKee", "Mabury",
           "Lundy", "Holger", "Zanker", "Montague", "Tasman", "Brokaw", "Oakland", "Jackson", "Coleman", "Guadalupe",
           "Bird", "Willow", "Lincoln", "Keyes", "San Carlos", "Stockton", "Union", "White", "Quimby", "Aborn",
           "Silver Creek", "Yerba Buena", "Snell", "Cottle", "Santa Teresa", "Bernal", "Coyote"]
_SUFFIX_WORDS = {s.lower() for s in STREET_SUFFIX.split("|")}
KNOWN_PLACES = sorted({n for n in NEIGHBORHOODS + STREETS
                       if not any(w.lower() in _SUFFIX_WORDS for w in n.split())} |
                      {n.rsplit(" ", 1)[0] for n in NEIGHBORHOODS if n.split()[-1].lower() in _SUFFIX_WORDS})
FUZZY_MIN = 85

# commenter_type cues (applied to the signature block / letterhead, not the whole body)
DEV_RE = re.compile(r"\b(attorneys? at law|law (?:firm|offices?|group)|LLP|LLC|L\.L\.C\.|counsel for|"
                    r"on behalf of (?:the |our client,? |my client,? )?(?:project )?(?:applicant|(?:property )?owner|developer|"
                    r"project sponsor|client))\b|\b(Consulting|Equities|Properties|Development|Developers?|Partners LP)\b", re.I)
DEV_CASE_WORDS = {"consulting", "equities", "properties", "development", "developer", "developers", "partners lp"}
GOV_RE = re.compile(r"\b(County of|Caltrans|VTA|Valley Water|Valley Transportation Authority|School District|"
                    r"Unified School|Union School District|USD\b|State of California|Assemblymember|Assembly ?member|"
                    r"State Senator|Board of Supervisors|Supervisor,? District|Santa Clara County Office of Education)\b"
                    r"|\bCity of (?!San Jos)[A-Z]")
ORG_RE = re.compile(
    r"\b(on behalf of|executive director|board of directors|president|chair(?:person)?|coalition|"
    r"association|chamber of commerce|foundation|alliance|council of|neighborhood association|homeowners|hoa|inc\.?|"
    r"corporation|nonprofit|non-profit|labor union|union local|local \d+|SEIU|committee|league|society|partnership|"
    r"institute|church|temple|congregation|network|collaborative|advocates|policy (?:&|and) advocacy|YWCA|YMCA|"
    r"organizing|organization|staff attorney|de-bug|SURJ|NAACP|ACLU|Catholic Charities|Sacred Heart)\b", re.I)
TITLE_WORDS = re.compile(r"\b(director|president|manager|associate|policy|advocacy|chair|coordinator|founder|member|"
                         r"resident|coalition|association|council|committee|organizer|officer|ceo|cfo|vp|board|"
                         r"commissioner|attorney|counsel|partner|principal|pastor|district|city|county|street|"
                         r"california|san|jose|josé|item|neighbor|community|inc|llc|llp)\b", re.I)
SIGNOFF_INLINE = re.compile(r"^(\s*(?:Sincerely(?: yours)?|Respectfully|Regards|Best regards|Kind regards|Warm regards|Best|"
                            r"Thanks|Thank you|In partnership|In solidarity|With gratitude|Cordially)[,!.]\s+)(\S.{2,120})$", re.I)
PERSON_LINE = re.compile(r"^[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]*){0,3},?$")


@dataclass
class Letter:
    comment_id: str
    item: str
    item_id: str
    item_title: str
    meeting_id: str
    meeting_date: str
    channel: str
    mock: bool
    received_at: str
    posted_raw: str
    stance: str
    stance_source: str
    neighborhood: str
    zip: str
    text: str
    source_url: str
    subject: str
    language: str
    commenter_type: str
    identity_hash: str
    duplicate_of: str | None
    ocr: bool
    has_address_hint: bool
    pdf_page_start: int
    pdf_page_end: int
    after_deadline: bool | None = None
    pdf_file: str = ""
    pages_total: int = 1
    pages_exhibit: int = 0


@dataclass
class Unit:
    """A split unit: chunks are (page_number, text) in page order; owned = pages counted toward this unit."""
    pdf_file: str
    chunks: list
    owned: list = field(default_factory=list)
    kind: str = "letter"  # letter | exhibit
    attached: list = field(default_factory=list)  # exhibit units attached to this letter

    @property
    def page_start(self) -> int:
        return self.chunks[0][0]

    @property
    def page_end(self) -> int:
        return max([self.chunks[-1][0]] + [u.page_end for u in self.attached])

    @property
    def text(self) -> str:
        return "\n".join(t for _, t in self.chunks)


# ----------------------------------------------------------------------------- text extraction

def have_tesseract() -> bool:
    return shutil.which("tesseract") is not None


def ocr_page(pdf_path: Path, page_index: int) -> str:
    import pypdfium2 as pdfium
    import pytesseract
    doc = pdfium.PdfDocument(str(pdf_path))
    page = doc[page_index]
    img = page.render(scale=2).to_pil()
    return pytesseract.image_to_string(img)


def extract_pages(pdf_path: Path, log, use_ocr: bool) -> list[dict]:
    cache = RAW_DIR / "textcache" / (pdf_path.stem + ".json")
    if cache.exists():
        cached = json.loads(cache.read_text())
        if cached.get("use_ocr") == use_ocr:
            return cached["pages"]
    pages = _extract_pages(pdf_path, log, use_ocr)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"use_ocr": use_ocr, "pages": pages}))
    return pages


def _extract_pages(pdf_path: Path, log, use_ocr: bool) -> list[dict]:
    import pdfplumber
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, p in enumerate(pdf.pages):
            try:
                t = p.extract_text() or ""
            except Exception:
                t = ""
            ocr = False
            if len(t.strip()) < MIN_CHARS:
                if use_ocr:
                    try:
                        t = ocr_page(pdf_path, i)
                        ocr = True
                    except Exception as e:
                        log(f"    ocr failed p{i + 1}: {e!r}")
                else:
                    ocr = None  # needed but unavailable
            pages.append({"n": i + 1, "text": t, "ocr": ocr})
    return pages


# ----------------------------------------------------------------------------- splitting + classification

def _nonempty(text: str) -> list[str]:
    return [l.strip() for l in text.split("\n") if l.strip()]


def is_wrapper_start(text: str) -> bool:
    """A Clerk-forward start page: the Outlook logo line ("Outlook", OCR'd "Ga Outlook") near the top.
    Web-print continuation pages only carry the "... - Outlook" print header, which this does not match."""
    return any(LOGO_RE.match(l) and " - " not in l for l in _nonempty(text)[:3])


def header_block_at(lines: list[str], i: int, strict: bool = False) -> bool:
    """True if lines[i] is 'From:' and a Sent:/Date:/Subject: line follows within 8 lines.
    strict: require an email 'Sent:' line (memo-style To:/From:/Subject:/Date: blocks inside a letter don't count)."""
    if not HDR_FROM.match(lines[i]):
        return False
    follow = HDR_SENT_ONLY if strict else HDR_FOLLOW
    return any(follow.match(l) for l in lines[i + 1:i + 9])


def outer_header_at(lines: list[str], i: int) -> bool:
    """Outlook-web header without colons: 'From X' followed by 'Date ...' within 4 lines."""
    if not OUT_FROM.match(lines[i]):
        return False
    return any(OUT_DATE.match(l) for l in lines[i + 1:i + 5])


def sent_block_at(lines: list[str], i: int) -> bool:
    """An inner 'Sent:' + 'Subject:' pair whose From: line was lost to OCR / redaction."""
    return bool(HDR_SENT_ONLY.match(lines[i])) and any(HDR_SUBJ.match(l) for l in lines[i + 1:i + 9])


def is_letter_text(text: str) -> bool:
    lines = [l for l in text.split("\n") if l.strip()][:LETTER_HEADER_WINDOW]
    if any(header_block_at(lines, i) or sent_block_at(lines, i) for i in range(len(lines))):
        return True
    # direct send: the Outlook header itself names a non-City sender, or (sender redacted) has no From line at all
    for i in range(min(len(lines), 15)):
        if outer_header_at(lines, i):
            return not FORWARDER.search(OUT_FROM.match(lines[i]).group(1))
        if OUT_DATE.match(lines[i]) and not any(OUT_FROM.match(l) for l in lines[max(0, i - 3):i]):
            return any(re.match(r"^\s*To\b", l) for l in lines[i + 1:i + 3])
    return False


def split_units(pages: list[dict], pdf_file: str = "") -> list[Unit]:
    """Split one PDF into units and classify each as letter / exhibit (exhibits attach to the preceding letter)."""
    if not pages:
        return []
    wrapper_pages = [p["n"] for p in pages if is_wrapper_start(p["text"])]
    units: list[Unit] = []
    if wrapper_pages:
        bounds = sorted(set([pages[0]["n"]] + wrapper_pages)) + [pages[-1]["n"] + 1]
        for a, b in zip(bounds, bounds[1:]):
            chunk = [(p["n"], p["text"]) for p in pages if a <= p["n"] < b]
            units.append(Unit(pdf_file, chunk, owned=[n for n, _ in chunk]))
    else:
        full, top = [], set()
        for p in pages:
            ne = 0
            for l in p["text"].split("\n"):
                if l.strip():
                    ne += 1
                if ne <= 6:
                    top.add(len(full))
                full.append((p["n"], l))
        lines = [l for _, l in full]
        # a new email starts at a top-of-page From: block, or anywhere at a From:+Sent: block
        raw_starts = [i for i in range(len(full)) if header_block_at(lines, i, strict=i not in top)]
        # a City forwarding layer (Agendadesk -> City Clerk -> sender) belongs to the email it forwards
        starts, pending = [], None
        for k, i in enumerate(raw_starts):
            nxt = raw_starts[k + 1] if k + 1 < len(raw_starts) else None
            if nxt is not None and nxt - i <= 25 and FORWARDER.search(HDR_FROM.match(lines[i]).group(1)):
                pending = i if pending is None else pending
                continue
            starts.append(i if pending is None else pending)
            pending = None
        if not starts or starts[0] > 10:
            starts = [0] + starts
        segs = []
        for a, b in zip(starts, starts[1:] + [len(full)]):
            seg = full[a:b]
            chunks: list = []
            for n, l in seg:
                if chunks and chunks[-1][0] == n:
                    chunks[-1][1].append(l)
                else:
                    chunks.append((n, [l]))
            segs.append([(n, "\n".join(ls)) for n, ls in chunks])
        for k, chunks in enumerate(segs):
            nxt = segs[k + 1][0][0] if k + 1 < len(segs) else None
            owned = [n for i, (n, _) in enumerate(chunks) if i == 0 or n != nxt]
            # a page shared with the next unit belongs to the next unit (it starts there) unless it is our first
            if len(chunks) > 1 and chunks[-1][0] == nxt:
                owned = [n for n in owned if n != nxt]
            units.append(Unit(pdf_file, chunks, owned=owned))
    out: list[Unit] = []
    for u in units:
        u.kind = "letter" if is_letter_text(u.text) else "exhibit"
        if u.kind == "exhibit" and out and out[-1].kind == "letter":
            out[-1].attached.append(u)
        else:
            out.append(u)
    return out


def split_emails(pages: list[dict]) -> list[tuple[int, int, str]]:
    """(page_start, page_end, text) per letter unit (exhibit units folded into the preceding letter)."""
    return [(u.page_start, u.page_end, u.text) for u in split_units(pages) if u.kind == "letter"]


def body_extent(unit: Unit) -> int:
    """Number of the unit's own chunks that hold the email body; the rest are exhibit pages."""
    texts = [t for _, t in unit.chunks]
    for k, t in enumerate(texts):
        if FOOTER.search(t):
            return k + 1
    for k, t in enumerate(texts[1:], start=1):
        if EXHIBIT_PAGE.match(t.lstrip()):
            return k
    if ATTACH_HDR.search("\n".join(texts[0].split("\n")[:60])):
        for k, t in enumerate(texts):
            if any(SIGNOFF.match(l) for l in t.split("\n")):
                return k + 1
        return 1
    return len(texts)


def letter_pages(unit: Unit) -> tuple[int, int, list[int], list[int]]:
    """(pages_total, pages_exhibit, body_pages, exhibit_pages) for a letter, incl. attached exhibit units."""
    k = body_extent(unit)
    body_pages = [n for n, _ in unit.chunks[:k] if n in unit.owned] or [unit.chunks[0][0]]
    ex = [n for n, _ in unit.chunks[k:] if n in unit.owned]
    for a in unit.attached:
        ex += a.owned
    return len(set(body_pages)) + len(set(ex)), len(set(ex)), body_pages, ex


def _walk_header(lines: list[str], i: int, line_re: re.Pattern) -> tuple[int, str, str]:
    """Walk a header block starting at lines[i]; returns (body_start, sent, subject)."""
    sent = subject = ""
    j, last_hdr = i + 1, i
    while j < len(lines) and j < i + 40:
        l = lines[j]
        if line_re.match(l) or HDR_LINE.match(l):
            last_hdr = j
            m = HDR_SENT.match(l) or OUT_DATE.match(l)
            if m and not sent:
                sent = m.group(m.lastindex).strip()
            m = HDR_SUBJ.match(l)
            if m:
                subject = m.group(1).strip()
                more = [k for k in range(j + 1, min(len(lines), j + 4)) if HDR_LINE.match(lines[k])]
                if not more:
                    break
                j = more[0]
                continue
        elif l.strip() in ("", ">") or re.search(r"<[^>]*@[^>]*>|@|[;,>]\s*$", l) or WRAPPER_NOISE.match(l.strip()):
            last_hdr = j  # wrapped recipient list / attachment lines
        else:
            break
        j += 1
    return last_hdr + 1, sent, subject


def parse_email(raw: str, page_start: int = 0, pages=None) -> dict:
    lines = raw.split("\n")
    subject = sender_line = sent = ""
    ne = _nonempty(raw)
    # wrapper subject = the line after the Outlook logo
    for k, l in enumerate(ne[:3]):
        if (LOGO_RE.match(l) or l.lower() == "outlook") and k + 1 < len(ne):
            subject = ne[k + 1]
            break
    blocks = [i for i in range(len(lines)) if header_block_at(lines, i)]
    # first inner block whose sender is not a City forwarding inbox and that carries text before the next block
    # (a staff "Fw:" with no note of its own is skipped); else the last block
    chosen = None
    for k, i in enumerate(blocks):
        if FORWARDER.search(HDR_FROM.match(lines[i]).group(1)):
            continue
        if k + 1 < len(blocks):
            bs = _walk_header(lines, i, HDR_LINE)[0]
            between = [l for l in lines[bs:blocks[k + 1]] if l.strip() and not BOILERPLATE.search(l)
                       and not WRAPPER_NOISE.match(l.strip())]
            if len(" ".join(between)) < 40:
                continue
        chosen = i
        break
    if chosen is None and blocks:
        chosen = blocks[-1]
    clerk_date = ""
    for i in range(min(len(lines), 30)):
        if outer_header_at(lines, i):
            clerk_date = next((OUT_DATE.match(l).group(1) for l in lines[i + 1:i + 5] if OUT_DATE.match(l)), "")
            break
    if chosen is not None:
        sender_line = HDR_FROM.match(lines[chosen]).group(1).strip()
        body_start, sent, subj = _walk_header(lines, chosen, HDR_LINE)
        subject = subj or subject
        if not parse_sent_dt(sent) and clerk_date:
            sent = clerk_date  # truncated / unreadable inner Sent: -> the Clerk's forward time
    elif any(sent_block_at(lines, i) for i in range(min(len(lines), 80))):
        i = next(i for i in range(min(len(lines), 80)) if sent_block_at(lines, i))
        body_start, sent, subj = _walk_header(lines, i, HDR_LINE)  # sender's From: line lost to OCR
        subject = subj or subject
        if not parse_sent_dt(sent) and clerk_date:
            sent = clerk_date
    else:
        outer = next((i for i in range(min(len(lines), 60)) if outer_header_at(lines, i)
                      or (OUT_DATE.match(lines[i]) and i < 15)), None)
        if outer is not None:  # direct send to the Clerk: the Outlook header is the sender's header
            m = OUT_FROM.match(lines[outer])
            sender_line = m.group(1).strip() if m else ""
            body_start, sent, _ = _walk_header(lines, outer, OUT_LINE)
        else:
            body_start = 0
            for i, l in enumerate(lines[:12]):
                if re.match(r"^\s*(From|Date|To)\s", l) or WRAPPER_NOISE.match(l.strip()):
                    body_start = i + 1
    body_lines = lines[body_start:]
    # cut at the next quoted header block (reply chains)
    cut = len(body_lines)
    for i in range(len(body_lines)):
        if header_block_at(body_lines, i, strict=True) or outer_header_at(body_lines, i) or INNER_CUT.match(body_lines[i]):
            cut = i
            break
    body_lines = body_lines[:cut]
    body = "\n".join(l for l in body_lines if not WRAPPER_NOISE.match(l.strip()) and not BOILERPLATE.search(l))
    m = EXHIBIT_PAGE.search(body)
    if m and m.start() > 200:
        body = body[:m.start()]
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    subject = re.sub(r"^(?:(?:FW|FWD|RE|Fwd|Re|Fw)\s*:\s*)+", "", subject).strip()
    return {"subject": subject, "sender_line": sender_line, "sent": sent, "body": body}


def clean_exhibit_text(text: str) -> str:
    t = "\n".join(l for l in text.split("\n") if not WRAPPER_NOISE.match(l.strip()) and not BOILERPLATE.search(l))
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


# ----------------------------------------------------------------------------- PII + signals

def parse_sent_dt(s: str) -> datetime | None:
    s = re.sub(r"(\d)(AM|PM)\b", r"\1 \2", (s or "").strip(), flags=re.I)
    s = re.sub(r"\s+", " ", s)
    for fmt in ("%A, %B %d, %Y %I:%M %p", "%A, %B %d, %Y %I:%M:%S %p", "%a %m/%d/%Y %I:%M %p", "%B %d, %Y %I:%M %p",
                "%m/%d/%Y %I:%M %p", "%A, %B %d, %Y %H:%M"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=TZ)
        except ValueError:
            continue
    return None


def parse_sent(s: str) -> str:
    dt = parse_sent_dt(s)
    return dt.isoformat(timespec="seconds") if dt else ""


def parse_deadline(s: str | None) -> datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if len(s) == 10:  # date only -> end of that day
        dt = dt.replace(hour=23, minute=59, second=59)
    return dt if dt.tzinfo else dt.replace(tzinfo=TZ)


def after_deadline(received_at: str, deadline: str | None) -> bool | None:
    dl = parse_deadline(deadline)
    if not dl or not received_at:
        return None
    try:
        return datetime.fromisoformat(received_at) > dl
    except ValueError:
        return None


def identity(sender_line: str) -> tuple[str, str, str]:
    em = EMAIL_RE.search(sender_line)
    email = em.group(0).lower() if em else ""
    name = EMAIL_RE.sub("", sender_line).replace("<", "").replace(">", "")
    name = re.split(r"[|\[\]{}()¢©_—]", name)[0]
    toks = name.split()
    while toks and (len(re.sub(r"\W", "", toks[-1])) <= 2 or not re.search(r"[A-Za-z]{2}", toks[-1])):
        toks.pop()  # OCR junk after the name: "Refugio Moreno a;", "Gianella Ordone:"
    name = " ".join(toks).strip(" ;,:|.'")
    key = (email or name.lower()).strip()
    h = "sha256:" + hashlib.sha256(key.encode()).hexdigest()[:16] if key else ""
    return name, email, h


def _looks_like_person(s: str) -> bool:
    s = s.strip(" |,;:.'’!")
    if re.search(r"\s(?:&|and)\s", s):  # "Susan Hayase and Tom Izu"
        return all(_looks_like_person(x) for x in re.split(r"\s(?:&|and)\s", s))
    return bool(s) and len(s) <= 40 and bool(PERSON_LINE.match(s)) and not TITLE_WORDS.search(s) and not ORG_RE.search(s)


def _scrub_name_line(s: str) -> str:
    m = re.search(r"\s*[|,]\s*|\s+-\s+", s)
    head, sep, tail = (s[:m.start()], m.group(0), s[m.end():]) if m else (s, "", "")
    if re.match(r"^\s*(California|CA)\b|^\s*\d{5}", tail) or len(head.split()) < 2:
        return s  # "Sacramento, California 95832" is a place; single words are left to the sender-name pass
    if _looks_like_person(head):
        return "[name removed]" + (sep + tail if tail and not _looks_like_person(tail) else "")
    return s


_LEFTOVER = re.compile(r"(?:\b[A-Z][a-zñé'’.-]+\s+)?\[name removed\](?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-zñé'’-]+\b)?(?:\s+Jr\.?)?")


def _collapse_leftovers(line: str) -> str:
    """"Minh [name removed]" / "[name removed] V. [name removed]" / "[name removed] Neale" -> "[name removed]"."""
    def fix(m):
        words = re.findall(r"[A-Za-z][a-zñé'’.-]+", m.group(0).replace("[name removed]", " "))
        return m.group(0) if any(TITLE_WORDS.search(w) or ORG_RE.search(w) for w in words) else "[name removed]"
    prev = None
    while prev != line:
        prev, line = line, _LEFTOVER.sub(fix, line)
        line = re.sub(r"\[name removed\](?:\s+\[name removed\])+", "[name removed]", line)
    return line


def _scrub_signoff_names(body: str, name_parts: list[str] | None = None) -> str:
    """Drop person names in the lines right after a sign-off ("Thanks,\\nRob LaNoce", "Ana Ruiz | Policy Associate"),
    plus any token of the sender's name there ("Wes")."""
    lines = body.split("\n")
    parts_re = (re.compile(r"\b(" + "|".join(re.escape(p) for p in name_parts) + r")\b", re.I) if name_parts else None)
    region: set[int] = set()
    nonempty = [i for i, l in enumerate(lines) if l.strip()]
    region.update(nonempty[-8:])  # the signature tail, sign-off or not
    for i, l in enumerate(lines):
        m = SIGNOFF_INLINE.match(l)
        if m:  # "Regards, Karlen Kirkland & Bianca Avanzo Kirkland"
            lines[i] = m.group(1) + _scrub_name_line(m.group(2))
        if not SIGNOFF.match(l) and not m:
            continue
        seen = 0
        for j in range(i + 1, min(len(lines), i + 9)):
            s = lines[j].strip()
            if not s or s.startswith("{First"):
                continue
            seen += 1
            if seen > 4:
                break
            lines[j] = _scrub_name_line(s)
            region.add(j)
    for j in sorted(region):
        if parts_re:
            lines[j] = parts_re.sub("[name removed]", lines[j])
        lines[j] = _collapse_leftovers(lines[j])
    return "\n".join(lines)


def scrub(body: str, name: str) -> str:
    body = EMAIL_RE.sub("[email removed]", body)
    body = PHONE_RE.sub("[phone removed]", body)
    if name and len(name) > 3:
        parts = [p for p in re.split(r"\s+", name) if len(p) > 2]
        body = re.sub(re.escape(name), "[name removed]", body, flags=re.I)
        if len(parts) >= 2:  # "First Last" signature variants
            body = re.sub(r"\b" + r"\s+".join(re.escape(p) for p in parts) + r"\b", "[name removed]", body, flags=re.I)
    parts = [p for p in re.split(r"[\s.]+", name or "") if len(p) >= 3 and re.match(r"^[A-Za-z'’-]+$", p)]
    return _scrub_signoff_names(body, parts)


def fuzzy_fix_place(s: str) -> tuple[str, bool]:
    """Correct OCR'd street / neighborhood names in a location hint ("Helger Way" -> "Holger Way")."""
    from rapidfuzz import fuzz
    if not s:
        return s, False
    toks = list(re.finditer(r"[A-Za-z][A-Za-z'’.-]*", s))
    known_lc = {k.lower(): k for k in KNOWN_PLACES}
    out, pos, changed, i = [], 0, False, 0
    while i < len(toks):
        done = False
        for n in (2, 1):
            if i + n > len(toks):
                continue
            span = toks[i:i + n]
            cand = " ".join(t.group(0) for t in span)
            cl = cand.lower().rstrip(".")
            words = cl.split()
            if any(w in _SUFFIX_WORDS for w in words) or len(cl.replace(" ", "")) < 4:
                continue
            if cl in known_lc:  # already right; leave as is
                i += n
                done = True
                break
            nxt = toks[i + n].group(0).lower().rstrip(".") if i + n < len(toks) else ""
            suffix = " " + nxt if nxt in _SUFFIX_WORDS else ""
            best, best_score = None, 0.0
            for k in KNOWN_PLACES:
                kl = k.lower()
                if len(kl.split()) != n or kl[0] != cl[0] or cl == kl + "s":
                    continue
                core = fuzz.ratio(cl, kl)
                score = max(core, fuzz.ratio(cl + suffix, kl + suffix) if suffix and core >= 75 else 0)
                if score > best_score:
                    best, best_score = k, score
            if best and best_score >= FUZZY_MIN:
                out.append(s[pos:span[0].start()])
                out.append(best)
                pos = span[-1].end()
                changed = True
                i += n
                done = True
                break
        if not done:
            i += 1
    out.append(s[pos:])
    return "".join(out), changed


def location_hints(body: str) -> dict:
    sig = "\n".join(body.split("\n")[-10:])
    addr = STREET_RE.search(sig)
    cross = CROSS_RE.search(body)
    z = ZIP_RE.search(sig)
    n = NEIGH_RE.search(body)
    return {"address": addr.group(0) if addr else "", "cross_street": f"{cross.group(1)} & {cross.group(2)}" if cross else "",
            "zip": z.group(1) if z else "", "neighborhood": n.group(1).title() if n else ""}


def signature_block(body: str) -> str:
    """Lines after the last sign-off (up to 12), else the last 3 non-empty lines."""
    lines = [l for l in body.split("\n") if l.strip()]
    idx = [i for i, l in enumerate(lines) if SIGNOFF.match(l)]
    if idx:
        return "\n".join(lines[idx[-1]:idx[-1] + 13])
    return "\n".join(lines[-3:])


def commenter_type(sender_line: str, email: str, body: str, exhibit_text: str = "") -> str:
    """resident | organization | developer_or_counsel | government, from signature-block / letterhead cues."""
    domain = email.split("@")[-1] if email else ""
    ex_lines = [l for l in exhibit_text.split("\n") if l.strip()]
    letterhead = "\n".join(ex_lines[:4])
    sig = "\n".join([sender_line, signature_block(body), signature_block("\n".join(ex_lines)) if ex_lines else "", letterhead])
    opening = body[:800] + "\n" + "\n".join(ex_lines[:25])

    def dev_hit(text: str) -> bool:
        for m in DEV_RE.finditer(text):
            if re.search(r"\bnot an? $", text[max(0, m.start() - 8):m.start()], re.I):
                continue  # "PHP is not a law firm"
            if m.group(2) and m.group(2).lower() in DEV_CASE_WORDS and not m.group(2)[0].isupper():
                continue  # "Development"/"Properties" only as a capitalized firm-name word
            return True
        return False

    if dev_hit(sig) or re.search(r"\bon behalf of (?:the |our client,? |my client,? )?(?:project )?(?:applicant|"
                                 r"(?:property )?owners?|developer|project sponsor)\b", opening, re.I):
        return "developer_or_counsel"
    city_inbox = domain.endswith("sanjoseca.gov")
    platform = domain.endswith(ADVOCACY_PLATFORMS)
    if (domain and not city_inbox and not platform and re.search(r"\.(gov|us)$", domain)) or GOV_RE.search(sig):
        return "government"
    if ORG_RE.search(sig) or re.search(r"\bon behalf of\b", opening, re.I):
        return "organization"
    if (domain and domain not in PERSONAL_DOMAINS and not domain.endswith(".edu") and not city_inbox
            and not domain.endswith(ADVOCACY_PLATFORMS)):
        return "organization"
    return "resident"


def detect_lang(text: str) -> str:
    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0
        return detect(text[:2000]) if len(text) > 40 else "en"
    except Exception:
        return "en"


def mark_duplicates(rows: list[Letter]) -> None:
    seen: dict[str, int] = {}
    for r in rows:
        base = r.comment_id
        n = seen.get(base, 0)
        seen[base] = n + 1
        if n:
            r.comment_id = f"{base}-{n + 1}"
            r.duplicate_of = base


TYPE_NOUN = {"resident": ("resident", "residents"), "organization": ("organization", "organizations"),
             "developer_or_counsel": ("developer/counsel", "developers/counsel"),
             "government": ("government agency", "government agencies")}


def pages_summary(pages_by_type: dict, letters_by_type: dict, senders_by_type: dict | None = None) -> str:
    """One human line, e.g. "94% of pages from 2 organizations; 1 resident letter"."""
    total = sum(pages_by_type.values())
    if not total:
        return "no letters"
    senders_by_type = senders_by_type or letters_by_type
    ranked = sorted((t for t in pages_by_type if pages_by_type[t]), key=lambda t: (-pages_by_type[t], COMMENTER_TYPES.index(t)))
    top = ranked[0]
    pct = round(100 * pages_by_type[top] / total)
    n = senders_by_type.get(top) or letters_by_type.get(top, 0)
    parts = [f"{pct}% of pages from {n} {TYPE_NOUN[top][0 if n == 1 else 1]}"]
    for t in ranked[1:]:
        k = letters_by_type.get(t, 0)
        parts.append(f"{k} {TYPE_NOUN[t][0]} letter{'s' if k != 1 else ''}")
    return "; ".join(parts)


# ----------------------------------------------------------------------------- items

def load_items(path: Path = ITEMS_CSV) -> list[dict]:
    with path.open(newline="") as f:
        items = [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]
    enrich: dict = {}
    if ITEMS_JSON.exists():
        for r in json.loads(ITEMS_JSON.read_text()).get("items", []):
            e = enrich.setdefault(r["matter_file"], {"matter_id": r.get("matter_id"), "event_id": r.get("event_id"),
                                                     "priority": r.get("priority", False), "attachments": {}})
            if r.get("pdf_path"):
                e["attachments"][Path(r["pdf_path"]).name] = r.get("attachment_url", "")
    for it in items:
        e = enrich.get(it["matter_file"], {})
        m = re.search(r"[?&]ID=(\d+)", it.get("legistar_url", ""))
        it["item_id"] = str(e.get("matter_id") or (m.group(1) if m else ""))
        it["meeting_id"] = str(e.get("event_id") or "")
        it["priority"] = bool(e.get("priority", False))
        it["attachment_urls"] = e.get("attachments", {})
        it["pdfs"] = sorted((RAW_DIR / it["matter_file"]).glob("*.pdf"))
    return items


# ----------------------------------------------------------------------------- main

def process_item(it: dict, log, use_ocr: bool, hints: dict) -> tuple[list[Letter], dict]:
    rows: list[Letter] = []
    n_pages = n_ocr = n_missing = unattributed = 0
    pages_by_type: Counter = Counter()
    pdf_meta = []
    for pdf in it["pdfs"]:
        pages = extract_pages(pdf, log, use_ocr)
        n_pages += len(pages)
        n_ocr += sum(1 for p in pages if p["ocr"])
        n_missing += sum(1 for p in pages if p["ocr"] is None)
        page_ocr = {p["n"]: p["ocr"] for p in pages}
        page_text = {p["n"]: p["text"] for p in pages}
        units = split_units(pages, pdf.name)
        pdf_letters = 0
        for u in units:
            if u.kind != "letter":
                unattributed += len(u.owned)
                continue
            total, n_ex, body_pages, ex_pages = letter_pages(u)
            k = body_extent(u)
            e = parse_email("\n".join(t for _, t in u.chunks[:k]))
            body = e["body"]
            ex_text = "\n".join(clean_exhibit_text(page_text[n]) for n in ex_pages[:2])
            if len(body) < SHORT_BODY and ex_text:
                body = (body + "\n\n" + ex_text).strip()
            if len(body) < 40:
                unattributed += total
                continue
            name, email, ih = identity(e["sender_line"])
            text = scrub(body, name)[:MAX_BODY]
            subject = scrub(e["subject"], name)
            loc = location_hints(body)
            ctype = commenter_type(e["sender_line"], email, e["body"], ex_text)
            received = parse_sent(e["sent"])
            cid = "L" + hashlib.sha1((it["matter_file"] + text).encode("utf-8")).hexdigest()[:8]
            rows.append(Letter(
                comment_id=cid, item=it["matter_file"], item_id=it["item_id"], item_title=it["title"],
                meeting_id=it["meeting_id"], meeting_date=it["meeting_date"], channel="letter", mock=False,
                received_at=received, posted_raw=e["sent"], stance="unclear", stance_source="pending_llm",
                neighborhood=loc["neighborhood"], zip=loc["zip"], text=text, source_url=it["legistar_url"],
                subject=subject, language=detect_lang(text), commenter_type=ctype, identity_hash=ih,
                duplicate_of=None, ocr=any(page_ocr.get(n) for n in body_pages + ex_pages),
                has_address_hint=bool(loc["address"] or loc["cross_street"]), pdf_page_start=u.page_start,
                pdf_page_end=u.page_end, after_deadline=after_deadline(received, it.get("comment_deadline")),
                pdf_file=pdf.name, pages_total=total, pages_exhibit=n_ex))
            pages_by_type[ctype] += total
            pdf_letters += 1
            if loc["address"] or loc["cross_street"]:
                addr, c1 = fuzzy_fix_place(loc["address"])
                cross, c2 = fuzzy_fix_place(loc["cross_street"])
                h = {"address": addr, "cross_street": cross, "zip": loc["zip"], "item": it["matter_file"],
                     "location_hint_corrected": c1 or c2}
                if c1 or c2:
                    h["address_ocr"], h["cross_street_ocr"] = loc["address"], loc["cross_street"]
                hints[cid] = h
        pdf_meta.append({"pdf_file": pdf.name, "pages": len(pages), "letters": pdf_letters,
                         "attachment_url": it["attachment_urls"].get(pdf.name, "")})
    mark_duplicates(rows)
    letters_by_type = Counter(r.commenter_type for r in rows)
    senders_by_type = {t: len({r.identity_hash or r.comment_id for r in rows if r.commenter_type == t}) for t in letters_by_type}
    pbt = {t: pages_by_type[t] for t in COMMENTER_TYPES if pages_by_type[t]}
    lbt = {t: letters_by_type[t] for t in COMMENTER_TYPES if letters_by_type[t]}
    meta = {"item": it["matter_file"], "item_id": it["item_id"], "item_title": it["title"], "meeting_id": it["meeting_id"],
            "meeting_date": it["meeting_date"], "body": it.get("body", ""), "agenda_number": it.get("agenda_number") or None,
            "priority": it["priority"], "source_url": it["legistar_url"],
            "attachment_url": pdf_meta[0]["attachment_url"] if pdf_meta else "", "attachments": len(pdf_meta),
            "pdfs": pdf_meta, "comment_deadline": it.get("comment_deadline") or None,
            "pages": n_pages, "ocr_pages": n_ocr, "ocr_missing_pages": n_missing, "letters": len(rows),
            "exhibit_pages": sum(r.pages_exhibit for r in rows), "pages_unattributed": unattributed,
            "exact_duplicates": sum(1 for r in rows if r.duplicate_of),
            "organizations": letters_by_type["organization"],
            "letters_by_type": lbt, "pages_by_type": pbt,
            "pages_summary": pages_summary(pbt, lbt, senders_by_type),
            "after_deadline": {"true": sum(1 for r in rows if r.after_deadline is True),
                               "false": sum(1 for r in rows if r.after_deadline is False),
                               "null": sum(1 for r in rows if r.after_deadline is None)}}
    return rows, meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="copy the committed fixture to the outputs, no PDFs")
    ap.add_argument("--crawl", action="store_true", help="(stub) crawl Legistar for new PDFs")
    ap.add_argument("--items", type=Path, default=ITEMS_CSV, help="items.csv sidecar")
    ap.add_argument("--limit", type=int, default=None, help="process only the first N matters")
    ap.add_argument("--no-ocr", action="store_true")
    args = ap.parse_args(argv)
    log = lambda s: print(s, file=sys.stderr, flush=True)

    if args.crawl:
        print(CRAWL_MSG)
        return 2
    if args.offline or not args.items.exists():
        payload = json.loads(FIXTURE.read_text())
        log(f"[offline] {len(payload['comments'])} letters from fixture")
        write_outputs(payload["items"], [Letter(**c) for c in payload["comments"]], also_fixture=False)
        return 0

    items = [it for it in load_items(args.items) if it["pdfs"]]
    if args.limit:
        items = items[:args.limit]
    use_ocr = have_tesseract() and not args.no_ocr
    log(f"{len(items)} matters, {sum(len(it['pdfs']) for it in items)} PDFs; OCR {'on' if use_ocr else 'OFF (tesseract not found)'}")
    hints: dict = {}
    all_rows, metas = [], []
    for it in items:
        rows, meta = process_item(it, log, use_ocr, hints)
        log(f"  {it['matter_file']} {it['meeting_date']} pdfs={meta['attachments']} p={meta['pages']} letters={meta['letters']} "
            f"exhibit_p={meta['exhibit_pages']} unattrib_p={meta['pages_unattributed']} | {meta['pages_summary']}")
        all_rows.extend(rows)
        metas.append(meta)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    HINTS_OUT.write_text(json.dumps(hints, indent=1))
    write_outputs(metas, all_rows, also_fixture=True)
    log(f"wrote {len(all_rows)} letters from {len(metas)} matters; ocr letters={sum(1 for r in all_rows if r.ocr)}; "
        f"address hints={len(hints)} (raw only; fuzzy-corrected={sum(1 for h in hints.values() if h['location_hint_corrected'])})")
    return 0


def write_outputs(metas: list[dict], rows: list[Letter], also_fixture: bool):
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))
    payload = {"generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
               "source": "Letters from the Public attached to San José City Council agenda items on Legistar (real; names, emails, phones removed at ingest)",
               "items": metas, "comments": [{k: asdict(r)[k] for k in FIELDS} for r in rows]}
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    if also_fixture:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(payload, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
