#!/usr/bin/env python3
"""Step a4: 311 problem reports per census tract by service type -> public/data/requests_311_types.json.

Same rows as requests_311_by_tract.json (problem categories only, located to a census tract, the same months), split
into the city's service types so the Problems map can filter below the section level. Labels follow the city's own
service type, except two catch-alls that are split by their sub-type:
  "Other Issues" -> its sub-type (Non-emergency police, Homeless concerns, Streets dispatch, ...)
  "RGR?CCC" (garbage/recycling)  -> junk pickup, containers, missed pickup, other garbage and recycling
Needs data/requests_311.csv (gitignored); without it the committed output is left as is.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "requests_311.csv"
BASE = ROOT / "public" / "data" / "requests_311_by_tract.json"
OUT = ROOT / "public" / "data" / "requests_311_types.json"

OTHER_LABEL = {"Other": "Other issues", "Streets Dispatch": "Streets dispatch", "Non-emergency police": "Non-emergency police",
               "Vehicle complaint": "Vehicle complaint", "SewerSanitation/WasteWater": "Sewer and wastewater",
               "Homeless concerns": "Homeless concerns", "Code Inquiry": "Code enforcement inquiry", "Building permit": "Building permit"}


def label(raw: str, sub: str) -> str:
    if raw == "Other Issues":
        return OTHER_LABEL.get(sub, sub or "Other issues")
    if raw == "RGR?CCC":
        s = sub or ""
        if s.startswith("Junk Item"):
            return "Junk pickup (recycling)"
        if s.startswith("Container Inquiry"):
            return "Garbage and recycling containers"
        if s.startswith("Missed Collection"):
            return "Missed garbage or recycling pickup"
        return "Other garbage and recycling"
    return raw


def main() -> int:
    if not SRC.exists():
        print(f"skip: {SRC.relative_to(ROOT)} not present; keeping {OUT.relative_to(ROOT)}")
        return 0
    base = json.loads(BASE.read_text())
    d = pd.read_csv(SRC, dtype=str, usecols=["created_at", "category_raw", "subcategory_raw", "category", "tract_id"]).fillna("")
    d = d[(d.category != "none") & (d.tract_id != "") & d.created_at.str[:7].isin(base["months"])].copy()
    d["label"] = [label(r, s) for r, s in zip(d.category_raw, d.subcategory_raw)]
    d["key"] = d.category + ":" + d.label.str.lower().map(lambda x: re.sub(r"[^a-z0-9]+", "_", x).strip("_"))
    types = (d.groupby(["key", "label", "category"]).size().reset_index(name="count").sort_values("count", ascending=False))
    by = {t: g.groupby("key").size().to_dict() for t, g in d.groupby("tract_id")}
    assert len(d) == sum(base["totals"].values()), "row count differs from requests_311_by_tract.json"
    OUT.write_text(json.dumps({"source": base["source"], "real": True, "months": base["months"], "months_covered": base["months_covered"],
                               "note": "311 problem reports per census tract by service type; same rows as requests_311_by_tract.json.",
                               "types": types.to_dict("records"), "by_tract": by}, separators=(",", ":")))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(types)} service types, {len(d)} reports, {OUT.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
