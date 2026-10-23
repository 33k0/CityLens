#!/usr/bin/env python3
"""Milestone 1: scrape Granicus eComments for San José City Council agenda items.

Public fields on sanjose.granicusideas.com (inspected 2026-10-23, see DECISIONS.md):
  - commenter display name   -> DROPPED at ingest (never written anywhere but data/raw/)
  - posted time (relative for old items, absolute for recent ones)
  - position label: Support / Oppose / Neutral
  - comment text
Not public: email, address, zip, neighborhood (collected by the form but not rendered).

Outputs (all PII-free):
  data/comments_raw.csv            one row per comment
  public/data/comments_raw.json    same rows + per-item metadata, used by the web app
  public/data/fixtures/ecomments.json  committed fixture used when --offline or network fails
Raw HTML goes to data/raw/ecomments/ (gitignored).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://sanjose.granicusideas.com"
UA = "CivicVoiceMap/0.1 (SJSU SpartHill hackathon; civic research; 1 req/s)"
RAW_DIR = ROOT / "data" / "raw" / "ecomments"
CSV_OUT = ROOT / "data" / "comments_raw.csv"
JSON_OUT = ROOT / "public" / "data" / "comments_raw.json"
FIXTURE = ROOT / "public" / "data" / "fixtures" / "ecomments.json"

# Chosen by comment count on 2026-10-23 (see DECISIONS.md). Meetings after Jan 2024 on this
# instance carry almost no eComments, so the largest housing / land-use / public-safety items
# from 2020-2023 are used.
DEFAULT_ITEMS = [
    ("2023-06-06_8.4", f"{BASE}/meetings/5022-city-council/agenda_items/646fdf1a44253859c000c2d3-8-dot-4-23-842-city-initiatives-roadmap-recreational"),
    ("2023-06-06_8.5", None),  # resolved from meeting page by title match below
    ("2020-04-07_8.3", None),
    ("2022-01-25_4.1", None),
]
TITLE_HINTS = {
    "2023-06-06_8.5": ("5022-city-council", "23-843"),
    "2020-04-07_8.3": ("3842-city-council", "20-452"),
    "2022-01-25_4.1": ("4602-city-council", "22-045"),
    "2023-06-06_8.4": ("5022-city-council", "23-842"),
}

FIELDS = [
    "comment_id", "item", "item_id", "item_title", "meeting_id", "meeting_date",
    "channel", "mock", "received_at", "posted_raw", "stance", "stance_source",
    "neighborhood", "zip", "text", "source_url", "ecomment_id", "duplicate_of",
]


@dataclass
class Comment:
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
    ecomment_id: str
    duplicate_of: str | None = None


# ----------------------------------------------------------------------------- HTTP

class Fetcher:
    def __init__(self, delay: float = 1.0, retries: int = 4):
        import httpx
        self.client = httpx.Client(headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
        self.delay = delay
        self.retries = retries
        self._last = 0.0

    def get(self, url: str) -> str:
        for attempt in range(self.retries):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                r = self.client.get(url)
            except Exception as e:  # network down etc.
                if attempt == self.retries - 1:
                    raise
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 200:
                return r.text
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt * 2)
                continue
            r.raise_for_status()
        raise RuntimeError(f"gave up on {url}")


# ----------------------------------------------------------------------------- parsing

STANCE_MAP = {"support": "support", "oppose": "oppose", "neutral": "neutral"}
ABS_DATE = re.compile(r"at\s+(\w+ \d{1,2}, \d{4}) at\s+(\d{1,2}:\d{2}\s*[ap]m)", re.I)


def normalize_stance(label: str) -> str:
    return STANCE_MAP.get(label.strip().lower(), "unclear")


def parse_posted(raw: str, meeting_date: str) -> str:
    """Absolute ISO timestamp when the page gives one, else '' (relative 'over 3 years ago')."""
    m = ABS_DATE.search(raw)
    if not m:
        return ""
    try:
        dt = datetime.strptime(f"{m.group(1)} {m.group(2).replace(' ', '').upper()}", "%B %d, %Y %I:%M%p")
        return dt.strftime("%Y-%m-%dT%H:%M:00-07:00")
    except ValueError:
        return ""


def objectid_time(eid: str) -> str:
    """Granicus ecomment ids are Mongo ObjectIds; the first 4 bytes are the unix creation time."""
    try:
        ts = int(eid[:8], 16)
    except ValueError:
        return ""
    from datetime import timezone, timedelta
    return datetime.fromtimestamp(ts, tz=timezone(timedelta(hours=-7))).strftime("%Y-%m-%dT%H:%M:%S-07:00")


def make_comment_id(item_id: str, text: str) -> str:
    return "G" + hashlib.sha1((item_id + text).encode("utf-8")).hexdigest()[:8]


def parse_item_page(html: str, item: str, source_url: str) -> tuple[dict, list[Comment], int]:
    """Returns (item_meta, comments_on_this_page, max_page)."""
    soup = BeautifulSoup(html, "lxml")
    meeting = soup.select_one("section.meeting")
    meeting_id = meeting.get("id", "") if meeting else ""
    meeting_date = ""
    if meeting:
        t = meeting.select_one(".time")
        if t:
            m = re.search(r"(\w+ \d{1,2}, \d{4})", t.get_text(" ", strip=True))
            if m:
                meeting_date = datetime.strptime(m.group(1), "%B %d, %Y").strftime("%Y-%m-%d")
    ai = soup.select_one("div.agenda_item")
    item_id = ai.get("data-id", "") if ai else ""
    h4 = ai.select_one("h4") if ai else None
    item_title = re.sub(r"\s+", " ", h4.get_text(" ", strip=True)) if h4 else ""
    bc = soup.select_one("section.ecomments .breadcrumb")
    declared = 0
    if bc:
        m = re.search(r"(\d+)\s+Public Comments?", bc.get_text(" ", strip=True))
        declared = int(m.group(1)) if m else 0
    pages = [int(x) for x in re.findall(r"[?&]page=(\d+)", html)]
    max_page = max(pages) if pages else 1

    comments: list[Comment] = []
    for li in soup.select("ul.comments > li[id^=ecomment_]"):
        eid = li.get("data-id", "")
        label = li.select_one(".pull-right label.label")
        stance = normalize_stance(label.get_text()) if label else "unclear"
        ta = li.select_one("span.timeago")
        posted_raw = re.sub(r"\s+", " ", ta.get_text(" ", strip=True)) if ta else ""
        body = li.select_one("div.comment_body")
        if body:
            for br in body.find_all("br"):
                br.replace_with("\n")
            text = body.get_text("\n", strip=True)
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
        else:
            text = ""
        if not text:
            continue
        comments.append(Comment(
            comment_id=make_comment_id(item_id, text),
            item=item, item_id=item_id, item_title=item_title,
            meeting_id=meeting_id, meeting_date=meeting_date,
            channel="ecomment", mock=False,
            received_at=parse_posted(posted_raw, meeting_date) or objectid_time(eid), posted_raw=posted_raw,
            stance=stance, stance_source="self_reported",
            neighborhood="", zip="", text=text, source_url=source_url, ecomment_id=eid,
        ))
    meta = {"item": item, "item_id": item_id, "item_title": item_title, "meeting_id": meeting_id,
            "meeting_date": meeting_date, "declared_count": declared, "source_url": source_url}
    return meta, comments, max_page


# ----------------------------------------------------------------------------- resolving item urls

def resolve_item_url(fetcher: Fetcher, meeting_slug: str, number: str) -> str:
    page = 1
    while True:
        url = f"{BASE}/meetings/{meeting_slug}/agenda_items?page={page}"
        html = fetcher.get(url)
        soup = BeautifulSoup(html, "lxml")
        for a in soup.select("div.agenda_item h4 a"):
            if number in a.get_text():
                return BASE + a["href"]
        pages = [int(x) for x in re.findall(r"agenda_items\?page=(\d+)", html)]
        if page >= max(pages + [1]):
            raise RuntimeError(f"item {number} not found in {meeting_slug}")
        page += 1


# ----------------------------------------------------------------------------- main

def scrape_item(fetcher: Fetcher, item: str, url: str, max_pages: int | None, log) -> tuple[dict, list[Comment]]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    all_comments: list[Comment] = []
    meta = {}
    page = 1
    max_page = 1
    while True:
        page_url = url if page == 1 else f"{url}?page={page}"
        html = fetcher.get(page_url)
        meta_p, comments, mp = parse_item_page(html, item, url)
        (RAW_DIR / f"{meta_p['item_id'] or item}_p{page}.html").write_text(html)
        if page == 1:
            meta = meta_p
            max_page = mp
            log(f"  {item} '{meta['item_title'][:70]}' declared={meta['declared_count']} pages={max_page}")
        all_comments.extend(comments)
        if page >= max_page or (max_pages and page >= max_pages):
            break
        page += 1
    return meta, mark_exact_duplicates(all_comments, meta)


def mark_exact_duplicates(all_comments: list[Comment], meta: dict) -> list[Comment]:
    """Identical text within an item hashes to the same id. Keep every submission (they are
    distinct people) but suffix the id and point duplicate_of at the first one."""
    seen: dict[str, int] = {}
    unique: list[Comment] = []
    for c in all_comments:
        base = c.comment_id
        n = seen.get(base, 0)
        seen[base] = n + 1
        if n:
            c.comment_id = f"{base}-{n + 1}"
            c.duplicate_of = base
        unique.append(c)
    meta["scraped_count"] = len(unique)
    meta["exact_duplicates"] = sum(1 for c in unique if c.duplicate_of)
    meta["scraped_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    return unique


def reparse_raw(log) -> tuple[list[dict], list[Comment]]:
    """Rebuild outputs from cached raw pages (no network). Item key comes from the previous JSON."""
    prev = json.loads(JSON_OUT.read_text()) if JSON_OUT.exists() else {"items": []}
    key_by_item_id = {m["item_id"]: (m["item"], m["source_url"]) for m in prev["items"]}
    groups: dict[str, list[Path]] = {}
    for f in sorted(RAW_DIR.glob("*_p*.html")):
        groups.setdefault(f.name.rsplit("_p", 1)[0], []).append(f)
    items_meta, comments = [], []
    for item_id, files in groups.items():
        files.sort(key=lambda f: int(f.stem.rsplit("_p", 1)[1]))
        key, url = key_by_item_id.get(item_id, (item_id, ""))
        meta, cs = {}, []
        for i, f in enumerate(files):
            m, c, _ = parse_item_page(f.read_text(), key, url)
            if i == 0:
                meta = m
            cs.extend(c)
        cs = mark_exact_duplicates(cs, meta)
        log(f"  {key}: {len(cs)} comments from {len(files)} cached pages")
        items_meta.append(meta)
        comments.extend(cs)
    return items_meta, comments


def write_outputs(items_meta: list[dict], comments: list[Comment], also_fixture: bool):
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for c in comments:
            w.writerow(asdict(c))
    payload = {"generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
               "source": "sanjose.granicusideas.com eComments (real, PII dropped at ingest)",
               "items": items_meta, "comments": [asdict(c) for c in comments]}
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    if also_fixture:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(payload, ensure_ascii=False, indent=1))


def load_fixture() -> tuple[list[dict], list[Comment]]:
    payload = json.loads(FIXTURE.read_text())
    return payload["items"], [Comment(**c) for c in payload["comments"]]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--item-url", action="append", default=[], metavar="KEY=URL",
                    help="override/add an agenda item, e.g. 2026-10-20_8.1=https://sanjose.granicusideas.com/meetings/.../agenda_items/...")
    ap.add_argument("--only-overrides", action="store_true", help="scrape only --item-url items, not the defaults")
    ap.add_argument("--offline", action="store_true", help="use the committed fixture instead of the network")
    ap.add_argument("--max-pages", type=int, default=None, help="limit pages per item (testing)")
    ap.add_argument("--no-fixture", action="store_true", help="do not overwrite public/data/fixtures/ecomments.json")
    ap.add_argument("--from-raw", action="store_true", help="re-parse data/raw/ecomments/*.html instead of fetching")
    args = ap.parse_args(argv)
    log = lambda s: print(s, file=sys.stderr, flush=True)

    if args.offline:
        items_meta, comments = load_fixture()
        log(f"[offline] loaded fixture: {len(comments)} comments across {len(items_meta)} items")
        write_outputs(items_meta, comments, also_fixture=False)
        return 0

    if args.from_raw:
        items_meta, comments = reparse_raw(log)
        write_outputs(items_meta, comments, also_fixture=not args.no_fixture)
        log(f"[from-raw] wrote {len(comments)} comments")
        return 0

    targets: list[tuple[str, str | None]] = [] if args.only_overrides else list(DEFAULT_ITEMS)
    for ov in args.item_url:
        k, _, u = ov.partition("=")
        targets.append((k, u))

    try:
        fetcher = Fetcher()
        items_meta, comments = [], []
        for key, url in targets:
            if not url:
                slug, number = TITLE_HINTS[key]
                url = resolve_item_url(fetcher, slug, number)
            log(f"scraping {key} <- {url}")
            meta, cs = scrape_item(fetcher, key, url, args.max_pages, log)
            items_meta.append(meta)
            comments.extend(cs)
            log(f"  -> {len(cs)} comments")
    except Exception as e:
        log(f"!! network scrape failed ({e!r}); falling back to fixture")
        if not FIXTURE.exists():
            raise
        items_meta, comments = load_fixture()

    write_outputs(items_meta, comments, also_fixture=not args.no_fixture)
    by_stance = {}
    for c in comments:
        by_stance[c.stance] = by_stance.get(c.stance, 0) + 1
    log(f"wrote {len(comments)} comments -> {CSV_OUT.relative_to(ROOT)}, {JSON_OUT.relative_to(ROOT)}; stance={by_stance}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
