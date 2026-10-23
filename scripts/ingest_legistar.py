#!/usr/bin/env python3
"""Step a: inventory San José City Council agenda items on Legistar and download every
"Letters from the Public" PDF attached to them.

Primary path: Legistar Web API  https://webapi.legistar.com/v1/sanjose/
  Events?$filter=EventDate ge datetime'2025-01-01' and EventBodyName eq 'City Council'
  Events/{EventId}/EventItems?AgendaNote=1&MinutesNote=1&Attachments=1   (attachments inline)
  Matters/{MatterId}/Attachments                                           (used as a cross-check)
Fallback path (only if the API answers 401/404): HTML on sanjose.legistar.com
  Calendar.aspx -> MeetingDetail.aspx -> LegislationDetail.aspx, selectors after inspection.

Outputs:
  data/raw/legistar/<matter_file>/letters[_<att_id>].pdf   (gitignored, cached by attachment id)
  data/legistar_items.json   one row per (event item, letters attachment), PII-free
  public/data/fixtures/legistar_items.json  committed copy for offline runs
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
API = "https://webapi.legistar.com/v1/sanjose"
SITE = "https://sanjose.legistar.com"
UA = "CivicVoiceMap/0.1 (SJSU SpartHill hackathon; civic research; 1 req/s)"
RAW_DIR = ROOT / "data" / "raw" / "legistar"
ITEMS_OUT = ROOT / "data" / "legistar_items.json"
FIXTURE = ROOT / "public" / "data" / "fixtures" / "legistar_items.json"
LETTERS_RE = re.compile(r"letters?\s+from\s+the\s+public", re.I)
PRIORITY_RE = re.compile(
    r"\b(housing|rent|tenant|homeless|shelter|zoning|rezon|general plan|land use|planning|development|"
    r"ceqa|appeal|permit|density|adu|parking|transit|transportation|bike|pedestrian|street|road|vision zero|"
    r"traffic|bart|vta|airport|data center|interim housing|encampment|rv)\b", re.I)


class Client:
    def __init__(self, delay=1.0):
        self.c = httpx.Client(headers={"User-Agent": UA}, timeout=120, follow_redirects=True)
        self.delay = delay
        self._last = 0.0

    def _wait(self):
        w = self.delay - (time.monotonic() - self._last)
        if w > 0:
            time.sleep(w)
        self._last = time.monotonic()

    def get(self, url, **kw) -> httpx.Response:
        for attempt in range(5):
            self._wait()
            try:
                r = self.c.get(url, **kw)
            except httpx.HTTPError:
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt * 2)
                continue
            return r
        raise RuntimeError(f"gave up: {url}")

    def json(self, url, **kw):
        r = self.get(url, **kw)
        r.raise_for_status()
        return r.json()


def safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_") or "unknown"


def api_test_call(cli: Client, log) -> bool:
    r = cli.get(f"{API}/Events", params={"$top": 1})
    log(f"API test call Events?$top=1 -> HTTP {r.status_code}")
    return r.status_code == 200


def inventory_api(cli: Client, since: str, until: str, log) -> list[dict]:
    flt = f"EventDate ge datetime'{since}' and EventDate le datetime'{until}' and EventBodyName eq 'City Council'"
    events = cli.json(f"{API}/Events", params={"$filter": flt, "$orderby": "EventDate"})
    log(f"{len(events)} City Council events {since}..{until}")
    rows = []
    for ev in events:
        items = cli.json(f"{API}/Events/{ev['EventId']}/EventItems",
                         params={"AgendaNote": 1, "MinutesNote": 1, "Attachments": 1})
        for it in items:
            for a in it.get("EventItemMatterAttachments") or []:
                if not LETTERS_RE.search(a.get("MatterAttachmentName") or ""):
                    continue
                title = (it.get("EventItemTitle") or it.get("EventItemMatterName") or "").strip()
                rows.append({
                    "event_id": ev["EventId"],
                    "meeting_date": ev["EventDate"][:10],
                    "body": ev["EventBodyName"].strip(),
                    "agenda_number": it.get("EventItemAgendaNumber"),
                    "event_item_id": it.get("EventItemId"),
                    "matter_id": it.get("EventItemMatterId"),
                    "matter_file": it.get("EventItemMatterFile"),
                    "matter_type": it.get("EventItemMatterType"),
                    "title": title,
                    "priority": bool(PRIORITY_RE.search(title)),
                    "attachment_id": a["MatterAttachmentId"],
                    "attachment_name": a["MatterAttachmentName"],
                    "attachment_url": a["MatterAttachmentHyperlink"],
                    "legislation_url": f"{SITE}/LegislationDetail.aspx?ID={it.get('EventItemMatterId')}&GUID={it.get('EventItemMatterGuid', '')}",
                    "meeting_url": ev.get("EventInSiteURL"),
                })
    return rows


def inventory_html(cli: Client, since: str, until: str, log) -> list[dict]:
    """HTML fallback. Only exercised if the API is disabled for this client; selectors are kept in
    one place so they can be fixed after inspection (see DECISIONS.md)."""
    from bs4 import BeautifulSoup
    rows = []
    cal = cli.get(f"{SITE}/Calendar.aspx")
    soup = BeautifulSoup(cal.text, "lxml")
    for a in soup.select("a[href*='MeetingDetail.aspx']"):
        row = a.find_parent("tr")
        txt = row.get_text(" ", strip=True) if row else ""
        if "City Council" not in txt:
            continue
        m = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", txt)
        if not m:
            continue
        mm, dd, yy = m.group(1).split("/")
        d = f"{yy}-{int(mm):02d}-{int(dd):02d}"
        if not (since <= d <= until):
            continue
        md = cli.get(SITE + "/" + a["href"].lstrip("/"))
        ms = BeautifulSoup(md.text, "lxml")
        for la in ms.select("a[href*='LegislationDetail.aspx']"):
            ld = cli.get(SITE + "/" + la["href"].lstrip("/"))
            ls = BeautifulSoup(ld.text, "lxml")
            title_el = ls.select_one("#ctl00_ContentPlaceHolder1_lblTitle2")
            for att in ls.select("a[href*='View.ashx']"):
                if LETTERS_RE.search(att.get_text(" ", strip=True)):
                    rows.append({"event_id": None, "meeting_date": d, "body": "City Council",
                                 "agenda_number": None, "event_item_id": None, "matter_id": None,
                                 "matter_file": la.get_text(strip=True), "matter_type": None,
                                 "title": title_el.get_text(" ", strip=True) if title_el else "",
                                 "priority": False, "attachment_id": None,
                                 "attachment_name": att.get_text(" ", strip=True),
                                 "attachment_url": SITE + "/" + att["href"].lstrip("/"),
                                 "legislation_url": SITE + "/" + la["href"].lstrip("/"), "meeting_url": None})
    return rows


def pdf_pages(path: Path) -> int | None:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return len(pdf.pages)
    except Exception:
        return None


def download(cli: Client, rows: list[dict], log) -> None:
    for r in rows:
        d = RAW_DIR / safe_name(r["matter_file"] or f"matter_{r['matter_id']}")
        d.mkdir(parents=True, exist_ok=True)
        fn = d / (f"letters_{r['attachment_id']}.pdf" if r["attachment_id"] else f"letters_{safe_name(r['attachment_name'])}.pdf")
        r["pdf_path"] = str(fn.relative_to(ROOT))
        if fn.exists() and fn.stat().st_size > 0:
            r["pages"] = pdf_pages(fn)
            continue
        resp = cli.get(r["attachment_url"])
        if resp.status_code != 200 or not resp.content.startswith(b"%PDF"):
            log(f"  !! {r['matter_file']} {r['attachment_name']}: HTTP {resp.status_code}, not a PDF")
            r["pages"] = None
            continue
        fn.write_bytes(resp.content)
        r["pages"] = pdf_pages(fn)
        log(f"  {r['matter_file']} {r['attachment_name']}: {len(resp.content)//1024} KB, {r['pages']} pages")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default="2025-01-01")
    ap.add_argument("--until", default=date.today().isoformat())
    ap.add_argument("--offline", action="store_true", help="use the committed fixture, no network")
    ap.add_argument("--no-download", action="store_true", help="inventory only")
    args = ap.parse_args(argv)
    log = lambda s: print(s, file=sys.stderr, flush=True)

    if args.offline:
        rows = json.loads(FIXTURE.read_text())["items"]
        ITEMS_OUT.write_text(json.dumps({"items": rows}, indent=1))
        log(f"[offline] {len(rows)} letter attachments from fixture")
        return 0

    cli = Client()
    try:
        if api_test_call(cli, log):
            path = "api"
            rows = inventory_api(cli, args.since, args.until, log)
        else:
            path = "html"
            rows = inventory_html(cli, args.since, args.until, log)
    except Exception as e:
        log(f"!! inventory failed ({e!r}); using fixture")
        rows = json.loads(FIXTURE.read_text())["items"]
        path = "fixture"
    log(f"{len(rows)} letters-from-the-public attachments on {len({r['matter_id'] for r in rows})} matters via {path}")
    if not args.no_download and path != "fixture":
        download(cli, rows, log)
    payload = {"source_path": path, "since": args.since, "until": args.until,
               "generated_at": date.today().isoformat(), "items": rows}
    ITEMS_OUT.parent.mkdir(parents=True, exist_ok=True)
    ITEMS_OUT.write_text(json.dumps(payload, indent=1))
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(payload, indent=1))
    log("| matter | meeting | title | pages |\n|---|---|---|---|")
    for r in sorted(rows, key=lambda r: (r["meeting_date"], str(r["agenda_number"]))):
        log(f"| {r['matter_file']} | {r['meeting_date']} | {r['title'][:70]} | {r.get('pages')} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
