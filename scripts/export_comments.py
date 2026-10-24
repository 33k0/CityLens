#!/usr/bin/env python3
"""Step h: join the voice channels with locations and classifications -> public/data/comments.json.

Voice family only (letters + email + site). 311 never enters this file (channel separation rule).
Inputs, all keyed by comment_id; any missing input is tolerated and reported:
  data/comments_raw.csv     letters (real)          data/emails_raw.csv     emails (simulated)
  data/locations.csv        resolve_locations.py    data/classifications.csv  classify.py
  data/campaigns.json       classify.py (optional)  data/legistar_items.json / emails item titles
Output: public/data/comments.json  {generated_at, families, channels, items, comments}
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"
OUT = ROOT / "public" / "data" / "comments.json"
LETTERS_JSON = ROOT / "public" / "data" / "comments_raw.json"

KEEP = ["comment_id", "item", "item_title", "meeting_date", "channel", "mock", "received_at", "subject", "text", "language",
        "commenter_type", "duplicate_of", "after_deadline", "source_url", "submitted_via", "to_office", "ocr",
        "pdf_page_start", "pdf_page_end", "pages_total", "pages_exhibit"]


def read(p: Path) -> pd.DataFrame | None:
    return pd.read_csv(p, dtype=str, keep_default_na=False) if p.exists() else None


def main() -> int:
    log = lambda s: print(s, file=sys.stderr, flush=True)
    frames = []
    for name, p in [("letters", D / "comments_raw.csv"), ("emails", D / "emails_raw.csv"), ("site", D / "submissions_raw.csv")]:
        df = read(p)
        if df is None:
            log(f"  -- {name}: {p.relative_to(ROOT)} missing, skipped")
            continue
        frames.append(df)
        log(f"  {name}: {len(df)} rows")
    voice = pd.concat(frames, ignore_index=True, sort=False)
    assert not (voice["channel"] == "311").any(), "channel separation: 311 rows must never enter the voice export"
    for c in KEEP:
        if c not in voice.columns:
            voice[c] = ""
    voice = voice[KEEP].copy().fillna("")  # channel-specific columns (e.g. to_office) are blank, never NaN

    loc = read(D / "locations.csv")
    if loc is not None:
        cols = [c for c in ["comment_id", "tract_id", "location_precision", "location_source", "location_basis", "multi_tract", "council_district", "matched_name"] if c in loc.columns]
        voice = voice.merge(loc[cols], on="comment_id", how="left")
        log(f"  locations joined: {voice['tract_id'].replace('', pd.NA).notna().sum()} with a tract")
    else:
        log("  -- locations.csv missing: tract_id empty, precision 'none'")
    cls = read(D / "classifications.csv")
    if cls is not None:
        # classify.py owns these fields; its duplicate_of/language win when set, else keep the ingest values
        voice = voice.merge(cls, on="comment_id", how="left", suffixes=("", "_cls"))
        for c in ("duplicate_of", "language"):
            if f"{c}_cls" in voice.columns:
                newer = voice[f"{c}_cls"].fillna("").astype(str)
                voice[c] = newer.where(newer != "", voice[c])
                voice = voice.drop(columns=[f"{c}_cls"])
        log(f"  classifications joined: {(voice['category'].fillna('') != '').sum()} labeled")
    else:
        log("  -- classifications.csv missing: category empty, stance 'unclear'")

    for c, default in [("tract_id", ""), ("location_precision", "none"), ("location_basis", ""), ("multi_tract", "False"), ("council_district", ""),
                       ("category", ""), ("subcategory", ""), ("bob_task_id", ""), ("inherited_from", ""), ("confidence", ""), ("evidence_quote", ""), ("stance", "unclear"),
                       ("stance_source", "pending_llm"), ("stance_evidence", ""), ("campaign_id", ""), ("engine", "")]:
        if c not in voice.columns:
            voice[c] = default
        voice[c] = voice[c].fillna(default).replace("", default)

    def b(v):
        return str(v).strip().lower() in ("true", "1")

    recs = []
    for r in voice.to_dict(orient="records"):
        r["mock"] = b(r["mock"])
        r["ocr"] = b(r["ocr"])
        r["multi_tract"] = b(r["multi_tract"])
        r["duplicate_of"] = r["duplicate_of"] or None
        r["campaign_id"] = r["campaign_id"] or None
        r["tract_id"] = r["tract_id"] or None
        r["council_district"] = int(float(r["council_district"])) if str(r["council_district"]).strip() not in ("", "nan") else None
        r["confidence"] = float(r["confidence"]) if str(r["confidence"]).strip() not in ("", "nan") else None
        r["after_deadline"] = None if str(r["after_deadline"]).strip() in ("", "nan", "None") else b(r["after_deadline"])
        for k in ("pdf_page_start", "pdf_page_end", "pages_total", "pages_exhibit"):
            r[k] = int(float(r[k])) if str(r[k]).strip() not in ("", "nan") else None
        r["family"] = "voice"
        recs.append(r)

    items = {}
    letters_meta = json.loads(LETTERS_JSON.read_text())["items"] if LETTERS_JSON.exists() else []
    for m in letters_meta:
        items[m["item"]] = {"item": m["item"], "title": m["item_title"], "meeting_date": m["meeting_date"], "mock": False,
                            "source": "Legistar", "source_url": m.get("source_url"), "pages_summary": m.get("pages_summary")}
    for r in recs:
        if r["item"] not in items:
            items[r["item"]] = {"item": r["item"], "title": r["item_title"], "meeting_date": r["meeting_date"], "mock": r["mock"],
                                "source": "simulated" if r["mock"] else "Legistar", "source_url": r.get("source_url") or None, "pages_summary": None}
    for it in items.values():
        rows = [r for r in recs if r["item"] == it["item"]]
        it["count"] = len(rows)
        it["count_unique"] = len({(r["campaign_id"] or r["comment_id"]) for r in rows if not r["duplicate_of"]})
        it["channels"] = sorted({r["channel"] for r in rows})

    channels = {}
    for r in recs:
        c = channels.setdefault(r["channel"], {"count": 0, "mock": r["mock"], "precision": {}})
        c["count"] += 1
        c["precision"][r["location_precision"]] = c["precision"].get(r["location_precision"], 0) + 1
    cats_path = D / "categories.json"
    categories = []
    if cats_path.exists():
        raw = json.loads(cats_path.read_text())
        raw = raw.get("categories", raw) if isinstance(raw, dict) else raw
        categories = [{"key": c["key"], "label": c.get("label", c["key"]), "description": c.get("description", ""),
                       "subcategories": [{"key": x["key"], "label": x.get("label", x["key"]), "description": x.get("description", "")}
                                         for x in c.get("subcategories", [])]} for c in raw]
    campaigns_path = D / "campaigns.json"
    campaigns = json.loads(campaigns_path.read_text()) if campaigns_path.exists() else None
    payload = {"categories": categories, "campaigns": campaigns, "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"), "family": "voice",
               "note": "Voice family only. 311 lives in requests_311_by_tract.json and is never summed with these rows.",
               "channels": channels, "items": sorted(items.values(), key=lambda x: -x["count"]), "comments": recs}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1, allow_nan=False))  # browsers reject NaN
    log(f"wrote {OUT.relative_to(ROOT)}: {len(recs)} voice comments, {len(items)} items, channels={ {k: v['count'] for k, v in channels.items()} }")
    return 0


if __name__ == "__main__":
    sys.exit(main())
