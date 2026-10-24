#!/usr/bin/env python3
"""Step k: compact files the staff chat (IBM Bob, app-analyst skill) reasons from.

public/data/tract_profiles.csv  one row per census tract: ACS profile, council district, comments (voice family) in total
                                and per section, voice per 1,000, 311 problem reports per 1,000 a year in total and per
                                section (separate family), and the app's underheard / quiet flags.
public/data/area_index.json     council districts and named neighborhoods (with aliases) -> census tract ids, so the
                                chat can open "District 3" or "Downtown" as a region.
public/data/associations.json   Spearman rank correlations across census tracts between ACS attributes and measured
                                outcomes (comment rate, 311 rate per section). Census tract-level associations only:
                                they describe places, not people, and do not show cause.

Voice and 311 stay separate columns; nothing here adds them.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "public" / "data"


def main() -> int:
    ui = json.loads((PUB / "ui.json").read_text())["tracts"]
    cfg = json.loads((PUB / "config.json").read_text())
    com = json.loads((PUB / "comments.json").read_text())
    p311 = json.loads((PUB / "requests_311_by_tract.json").read_text())
    cats = [c["key"] for c in com["categories"]]
    months = p311["months_covered"]
    rows = [c for c in com["comments"] if not c.get("duplicate_of")]

    t = pd.DataFrame([{k: x[k] for k in ("id", "nbhd", "district", "pop", "households", "renter", "lep", "income",
                                          "nonwhite", "epc")} | {"spanish": (x.get("lang") or {}).get("spanish"),
                                                                 "asian_pacific": (x.get("lang") or {}).get("asian_pacific")}
                       for x in ui]).set_index("id")
    t["epc"] = t["epc"].isin(["High", "Higher", "Highest"])
    located = [c for c in rows if c.get("tract_id") in t.index]
    t["comments"] = pd.Series({i: 0 for i in t.index}).add(pd.Series([c["tract_id"] for c in located]).value_counts(), fill_value=0)
    for k in cats:
        s = pd.Series([c["tract_id"] for c in located if c["category"] == k]).value_counts()
        t[f"comments_{k}"] = pd.Series(0, index=t.index).add(s, fill_value=0).astype(int)
    t["comments"] = t["comments"].astype(int)
    per1k = lambda n: (n / t["pop"].where(t["pop"] > 0) * 1000).round(3)
    t["voice_per_1k"] = per1k(t["comments"])
    bt = p311["by_tract"]
    for k in cats + ["all"]:
        n = pd.Series({i: sum(sum(m.values()) for ck, m in bt.get(i, {}).items() if k == "all" or ck == k) for i in t.index})
        t["p311_per_1k_yr" if k == "all" else f"p311_{k}_per_1k_yr"] = (n / t["pop"].where(t["pop"] > 0) * 1000 * 12 / months).round(1)

    # the app's underheard rule (config.json), citywide, all sections
    U = cfg.get("underheard_rule", {})
    pop = t["pop"].sum()
    exp = t["pop"] / pop * len(located)
    c311 = (t["p311_per_1k_yr"].fillna(0) * t["pop"]).sum() / pop
    clep = (t["lep"] * t["households"].fillna(0)).sum() / t["households"].fillna(0).sum()
    low = (t["comments"] / exp.where(exp > 0)).fillna(1) < cfg.get("underrepresented_ratio", 0.5)
    prob = t["p311_per_1k_yr"].fillna(0) >= c311 * U.get("problems_vs_city", 1)
    lep = t["lep"] >= clep * U.get("limited_english_vs_city", 1.5)
    t["expected_comments"] = exp.round(1)
    t["underheard"] = low & (prob | lep)
    t["quiet"] = low & ~prob & ~lep
    t.index.name = "tract_id"
    t.to_csv(PUB / "tract_profiles.csv", quoting=csv.QUOTE_MINIMAL)

    nb = pd.read_csv(ROOT / "data" / "neighborhoods.csv", dtype=str).fillna("")
    areas = [{"name": r.name, "aliases": [a for a in r.aliases.split("|") if a],
              "tracts": [x for x in r.tract_ids.split("|") if x in t.index]} for r in nb.itertuples()]
    districts = {str(int(d)): sorted(t.index[t["district"] == d]) for d in sorted(t["district"].dropna().unique())}
    (PUB / "area_index.json").write_text(json.dumps({"note": "Council districts and named neighborhoods -> census tract ids "
                                                     "(neighborhood lists come from the city's neighborhood layer; one census tract can belong to several).",
                                                     "districts": districts, "areas": [a for a in areas if a["tracts"]]},
                                                    ensure_ascii=False, indent=1))

    attrs = {"income": "median household income", "renter": "renter share", "lep": "limited-English share",
             "nonwhite": "non-white share", "spanish": "Spanish-speaking households", "asian_pacific": "Asian/Pacific-language households",
             "epc": "Equity Priority Community"}
    outs = {"voice_per_1k": "comments per 1,000 (voice)", "p311_per_1k_yr": "311 problem reports per 1,000 a year (all)"}
    outs |= {f"p311_{k}_per_1k_yr": f"311 reports per 1,000 a year: {k}" for k in cats if t[f"p311_{k}_per_1k_yr"].fillna(0).sum() > 0}
    res = []
    d = t[t["pop"] > 0]
    for a, al in attrs.items():
        for o, ol in outs.items():
            x = d[[a, o]].dropna().astype(float)
            if len(x) < 20 or x[o].nunique() < 3:
                continue
            r, p = spearmanr(x[a], x[o])
            res.append({"attribute": a, "attribute_label": al, "outcome": o, "outcome_label": ol, "rho": round(float(r), 3),
                        "p": float(f"{p:.2g}"), "n": int(len(x)),
                        "strength": "strong" if abs(r) >= .5 else "moderate" if abs(r) >= .3 else "weak" if abs(r) >= .1 else "none"})
    (PUB / "associations.json").write_text(json.dumps({
        "method": "Spearman rank correlation across San José census tracts with residents (n≈213).",
        "read_as": "Census tract-level association between a place's ACS profile and what was measured there. It does not "
                   "describe individuals, does not show cause, and 311 volume also reflects who uses 311.",
        "caveat_voice": "Most comments are simulated emails (see metrics Q6), so voice associations are illustrative.",
        "results": sorted(res, key=lambda r: -abs(r["rho"]))}, indent=1))
    print(f"tract_profiles.csv {len(t)} rows; area_index {len(districts)} districts, {len(areas)} areas; associations {len(res)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
