#!/usr/bin/env python3
"""Step a6: San José police calls for service -> census tracts, same months as 311.

Input : data/raw/police/policecalls{2025,2026}.csv  (SJPD Calls for Service, data.sanjoseca.gov, CC0; one row per
        incident; locations are block ranges "[300]-[400] E SANTA CLARA ST" or intersections "A ST & B AV")
        data/raw/sjgis/street_ranges.json         (city street centerlines with left/right address ranges)
        public/data/tracts.geojson, public/data/requests_311_by_tract.json (months)
Output: public/data/police_by_tract.json  {months, groups, by_tract[tract][group][YYYY-MM], totals, city_monthly, coverage}

Police calls are a third family next to comments (voice) and 311 (problems): reported to police, not crimes, and they
also reflect where officers patrol and stop people. They are never added to comments or 311.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "public" / "data" / "police_by_tract.json"
FILES = [RAW / "police" / f"policecalls{y}.csv" for y in (2025, 2026)]

GROUPS = [  # first match wins; labels are what staff see
    ("violence", "Violence and weapons", r"ASSAULT|BATTERY|SHOOT|SHOTS|ROBBERY|STAB|WEAPON|ADW|HOMICIDE|RAPE|SEXUAL|KIDNAP|BRANDISH|CARJACK|GUN"),
    ("theft_property", "Theft and property", r"THEFT|BURGLARY|STOLEN|VANDAL|MALICIOUS MISCHIEF|SHOPLIFT|LOOT|EMBEZZ|FRAUD|FORGERY"),
    ("traffic", "Traffic and vehicles", r"VEHICLE STOP|RECKLESS|ACCIDENT|HIT AND RUN|TRAFFIC|PARKING|DUI|SPEED|ABANDONED VEH|TOW|DRAG RAC|SIDESHOW"),
    ("disturbance", "Disturbances and noise", r"DISTURB|NOISE|MUSIC|FIREWORK|FIGHT|ARGUMENT|PARTY"),
    ("welfare", "Welfare and mental health", r"WELFARE|MENTAL|5150|SUICID|OVERDOSE|MEDICAL|DRUNK|INTOX|MISSING|SICK|INJURED"),
    ("suspicious", "Suspicious activity and trespassing", r"SUSPICIOUS|TRESPASS|PROWL|LOITER"),
    ("alarm", "Alarms", r"ALARM"),
    ("other", "Other calls", r"."),
]
GRX = [(k, l, re.compile(p)) for k, l, p in GROUPS]
SUF = {"AVENUE": "AV", "AVE": "AV", "AV": "AV", "BOULEVARD": "BL", "BLVD": "BL", "BL": "BL", "STREET": "ST", "ST": "ST",
       "ROAD": "RD", "RD": "RD", "DRIVE": "DR", "DR": "DR", "LANE": "LN", "LN": "LN", "COURT": "CT", "CT": "CT",
       "PLACE": "PL", "PL": "PL", "WAY": "WY", "WY": "WY", "EXPRESSWAY": "EX", "EXPY": "EX", "EX": "EX", "PARKWAY": "PY",
       "PKWY": "PY", "PY": "PY", "CIRCLE": "CR", "CIR": "CR", "CR": "CR", "CL": "CR", "TERRACE": "TR", "TER": "TR", "HIGHWAY": "HY", "HWY": "HY",
       "SQUARE": "SQ", "SQ": "SQ", "LOOP": "LP", "LP": "LP", "ALLEY": "AL", "PLAZA": "PZ", "PLZ": "PZ"}


def norm(name: str) -> str:
    t = re.sub(r"[^A-Z0-9 ]", " ", str(name or "").upper()).split()
    if t and t[-1] in SUF:
        t[-1] = SUF[t[-1]]
    return " ".join(t)


def group(call_type: str) -> str:
    for k, _, rx in GRX:
        if rx.search(call_type or ""):
            return k
    return "other"


def main() -> int:
    if not all(f.exists() for f in FILES):
        print("skip: police call files not present; keeping", OUT.relative_to(ROOT))
        return 0
    months = json.loads((ROOT / "public/data/requests_311_by_tract.json").read_text())["months"]
    tracts = gpd.read_file(ROOT / "public/data/tracts.geojson")[["tract_id", "geometry"]]
    tree = STRtree(list(tracts.geometry))
    tids = list(tracts.tract_id)

    def tract_at(x, y):
        p = Point(x, y)
        for i in tree.query(p):
            if tracts.geometry.iloc[i].contains(p):
                return tids[i]
        return None

    streets = json.loads((RAW / "sjgis/street_ranges.json").read_text())["features"]
    by_name = defaultdict(list)          # name -> [(lo, hi, midpoint)]
    ends = defaultdict(set)              # name -> rounded endpoints
    for s in streets:
        n = norm(s["n"])
        pts = [p for path in s["p"] for p in path]
        if not n or not pts:
            continue
        nums = [v for v in (s["fl"], s["tl"], s["fr"], s["tr"]) if isinstance(v, (int, float)) and v > 0]
        mid = pts[len(pts) // 2]
        if nums:
            by_name[n].append((min(nums), max(nums), mid))
        for path in s["p"]:
            for q in (path[0], path[-1]):
                ends[n].add((round(q[0], 5), round(q[1], 5)))
    cache: dict[str, str | None] = {}
    BLOCK = re.compile(r"^\[(\d+)\]-\[(\d+)\]\s+(.+?)\s*$")

    def locate(addr: str):
        if addr in cache:
            return cache[addr]
        t = None
        m = BLOCK.match(addr)
        if m:
            lo, hi, name = int(m.group(1)), int(m.group(2)), norm(m.group(3))
            segs = by_name.get(name, [])
            # the published block is usually the hundred block; some rows drop the last digit of the street number
            # ("[600]-[700]" on a street numbered 6000-6400), so a block that matches nothing is tried at x10
            for a, b in ((lo, hi), (lo * 10, hi * 10)):
                hit = sorted((s for s in segs if s[0] < b and s[1] >= a), key=lambda s: s[0])
                if hit:
                    t = tract_at(*hit[len(hit) // 2][2])
                    break
        elif "&" in addr:
            a, b = [norm(x) for x in addr.split("&", 1)]
            common = ends.get(a, set()) & ends.get(b, set())
            if common:
                t = tract_at(*sorted(common)[0])
        cache[addr] = t
        return t

    by = defaultdict(lambda: defaultdict(Counter))
    city = defaultdict(Counter)
    seen = Counter()
    gcount = Counter()
    for f in FILES:
        with open(f, encoding="utf-8", errors="replace") as fh:
            for r in csv.DictReader(fh):
                mo = (r.get("REPORT_DATE") or "")[:7]
                if mo not in months:
                    continue
                g = group(r.get("CALL_TYPE", ""))
                city[g][mo] += 1
                gcount[g] += 1
                seen["calls"] += 1
                t = locate((r.get("ADDRESS") or "").strip())
                if t:
                    by[t][g][mo] += 1
                    seen["located"] += 1
                else:
                    seen["block" if BLOCK.match(r.get("ADDRESS") or "") else "intersection" if "&" in (r.get("ADDRESS") or "") else "blank"] += 1
    out = {"source": "San José Police Department, Calls for Service (data.sanjoseca.gov/dataset/police-calls-for-service, CC0)",
           "real": True, "family": "police",
           "note": "Calls for police service by report date, placed in census tracts from block ranges and intersections. Calls, not "
                   "crimes; they include officer-initiated stops and also reflect where officers patrol.",
           "months": months, "months_covered": len(months),
           "groups": [{"key": k, "label": l, "count": gcount[k]} for k, l, _ in GROUPS],
           "by_tract": {t: {g: dict(m) for g, m in gs.items()} for t, gs in by.items()},
           "totals": {t: sum(sum(m.values()) for m in gs.values()) for t, gs in by.items()},
           "city_monthly": {g: dict(m) for g, m in city.items()},
           "coverage": {"calls": seen["calls"], "located": seen["located"],
                        "unlocated": {k: seen[k] for k in ("block", "intersection", "blank")}}}
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT.relative_to(ROOT)}: {seen['calls']} calls in {len(months)} months, located {seen['located']} "
          f"({seen['located'] / max(1, seen['calls']):.1%}), unlocated {out['coverage']['unlocated']}; groups {dict(gcount)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
