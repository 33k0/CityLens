#!/usr/bin/env python3
"""Step i: compute every metric in docs/METRICS.md from the built data -> public/data/metrics.json.

Citywide, all items, no filters. Each metric carries its id, value(s), the formula used, and provenance
(real | illustrative). Reuses fairness.py's city model and unique-voice weights so the numbers match the
fairness exports exactly. Voice and 311 are never added together (families.sum_within_family guards it).
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fairness as FZ  # noqa: E402
import families as fam  # noqa: E402

PUB = ROOT / "public" / "data"
OUT = PUB / "metrics.json"


def load(p):
    return json.loads(Path(p).read_text())


def r1(x, n=1):
    return None if x is None else round(float(x), n)


def share(num, den, n=1):
    return None if not den else round(100 * num / den, n)


def gini(xs):
    xs = sorted(xs)
    n, s = len(xs), sum(xs)
    if not n or not s:
        return None
    return round(sum((2 * i - n + 1) * x for i, x in enumerate(xs)) / (n * s), 3)


def main() -> int:
    voice = load(PUB / "comments.json")
    rows = voice["comments"]
    cats = {c["key"]: c for c in voice["categories"]}
    clabel = {k: c["label"] for k, c in cats.items()}
    slabel = {s["key"]: s["label"] for c in voice["categories"] for s in c["subcategories"]}
    p311 = load(PUB / "requests_311_by_tract.json")
    vcity, pcity = load(PUB / "fairness" / "voice_city.json"), load(PUB / "fairness" / "311_city.json")
    meta, pwv = load(PUB / "fairness" / "meta.json"), load(PUB / "fairness" / "problems_without_voice.json")
    runs = load(ROOT / "data" / "bob_runs.json")["runs"]
    camp = load(ROOT / "data" / "campaigns.json")["campaigns"]
    pop = {t: int(v) for t, v in p311["population"].items()}
    tr = {r["tract_id"]: r for r in vcity["tracts"]}
    for t in tr:
        pop.setdefault(t, tr[t]["population"])
    total_pop = sum(pop.values())

    FZ.check_voice(rows)
    u = FZ.voice_row_weights(rows, "dedup")  # unique-voice weight per row (duplicates 0, campaign 1/n)
    for r, w in zip(rows, u):
        r["_u"] = w
    U = lambda rs: sum(r["_u"] for r in rs)  # noqa: E731
    mock_any = any(r["mock"] for r in rows)
    vlabel = "illustrative" if mock_any else "real"
    M = {}

    def put(mid, name, value, formula, label, **extra):
        M[mid] = {"id": mid, "name": name, "value": value, "formula": formula, "label": label, **extra}

    # ------------------------------------------------------------------ Tier 1
    by_ch = Counter(r["channel"] for r in rows)
    put("H1", "Voice comments (rows)", len(rows), "|V|", vlabel, by_channel=dict(by_ch))
    put("H2", "Unique voices", r1(U(rows), 1), "Σ u(r)", vlabel,
        by_channel={c: r1(U([r for r in rows if r["channel"] == c]), 1) for c in by_ch})
    P_cat = Counter()
    for t, cs in p311["by_tract"].items():
        for c, m in cs.items():
            P_cat[c] += sum(m.values())
    P = sum(P_cat.values())
    put("H3", "311 problem reports (located)", P, "Σ by_tract[t][c][m]", "real", since=p311["since"])
    Uall = U(rows)
    put("H4", "Category share, voice (%)", {clabel[c]: share(U([r for r in rows if r["category"] == c]), Uall) for c in cats},
        "100·U(cat=c)/U(V)", vlabel)
    put("H5", "Category share, 311 (%)", {clabel.get(c, c): share(n, P) for c, n in P_cat.most_common()}, "100·P_c/ΣP", "real")
    sub = {}
    for c in cats:
        rc = [r for r in rows if r["category"] == c]
        uc = U(rc)
        sub[clabel[c]] = {slabel.get(s["key"], s["key"]): share(U([r for r in rc if r["subcategory"] == s["key"]]), uc)
                          for s in cats[c]["subcategories"]}
    put("H6", "Subcategory share within category (%)", sub, "100·U(cat=c∩sub=s)/U(cat=c)", vlabel)
    put("H7", "Stance distribution (% of unique voices)",
        {k: share(U([r for r in rows if r["stance"] == k]), Uall) for k in ("support", "oppose", "neutral", "unclear")},
        "100·U(stance=k)/U(V)", vlabel,
        raw_rows={k: sum(1 for r in rows if r["stance"] == k) for k in ("support", "oppose", "neutral", "unclear")})
    cov = {}
    for c in list(by_ch) + ["all"]:
        rc = rows if c == "all" else [r for r in rows if r["channel"] == c]
        cov[c] = {"located_pct": share(sum(1 for r in rc if r["tract_id"]), len(rc)),
                  "by_precision_pct": {k: share(n, len(rc)) for k, n in Counter(r["location_precision"] for r in rc).most_common()}}
    put("H8", "Location coverage (%)", cov, "100·|L|/|V| by channel and precision", vlabel)
    vr = [t["rate_per_1k"] for t in vcity["tracts"]]
    put("H9", "Voice participation rate per 1k (tract)",
        {"tracts_above_zero": sum(1 for x in vr if x > 0), "median": r1(st.median(vr), 3), "max": r1(max(vr), 3),
         "city_median": meta["city_median_rate_per_1k"]["voice"], "basis": meta["voice_location_basis"]},
        "1000·U(Res∩t)/pop(t)", vlabel)
    pr = list(p311["rate_per_1k_annualized"].values())
    put("H10", "311 problem rate per 1k per year (tract)",
        {"median": r1(st.median(pr)), "min": r1(min(pr)), "max": r1(max(pr)),
         "city_median": r1(meta["city_median_rate_per_1k"]["problems"])}, "1000·P_t/pop(t)·12/M", "real")
    ppct = fam.percentile_ranks({t: float(v) for t, v in p311["rate_per_1k_annualized"].items()})
    vpct = {t: tr[t]["percentile"] for t in tr}
    put("H11", "Voice and 311 percentiles (tract)",
        {"voice_pct_0_tracts": sum(1 for v in vpct.values() if v == 0), "voice_pct_max": r1(max(vpct.values())),
         "problem_pct_ge_70_tracts": sum(1 for v in ppct.values() if v is not None and v >= 70)},
        "100·|{t': x_t' < x_t}|/N", "illustrative (voice) / real (311)")
    for mid, key, nm in (("H12", "di", "Disparate impact"), ("H13", "spd", "Statistical parity difference")):
        val = {}
        for fname, src in (("voice", vcity), ("311", pcity)):
            val[fname] = {a: {"unweighted": r1(src["measure"][a]["unweighted"][key], 3),
                              "population_weighted": r1(src["measure"][a]["population_weighted"][key], 3)}
                          for a in FZ.ATTRIBUTES}
        put(mid, nm + " per family", val, "DI = P(fav|unpriv)/P(fav|priv); SPD = difference; AIF360, pandas 1e-9",
            "voice illustrative / 311 real", flag_rule="DI < 0.8 under-represented; > 1.25 over-represented")
    put("H14", "Problems without voice", {"tracts": len(pwv["rows"]), "top5": pwv["rows"][:5]},
        "problem_pct ≥ 70 and voice_pct ≤ 30", vlabel)

    # ------------------------------------------------------------------ Tier 2
    put("A1", "Campaigns", {"count": len(camp), "campaigns": [{"id": c["campaign_id"], "size": c["size"], "item": c["item"],
                                                               "distinct_senders": c["distinct_senders"]} for c in camp]},
        "MinHash/LSH components ≥ 2 rows", vlabel)
    located_u = defaultdict(float)
    for r in rows:
        if r["tract_id"]:
            located_u[r["tract_id"]] += r["_u"]
    silent = [t for t in pop if located_u.get(t, 0) == 0]
    put("A2", "Silent tracts", {"tracts": len(silent), "of": len(pop), "residents": sum(pop[t] for t in silent)},
        "tracts with U(L∩t)=0; Σ pop", vlabel)
    items = defaultdict(list)
    for r in rows:
        items[r["item"]].append(r)
    put("A3", "Campaign share of item (%)",
        {k: share(sum(1 for r in v if r["campaign_id"]), len(v)) for k, v in items.items() if any(r["campaign_id"] for r in v)},
        "100·|campaign rows|/|item rows|", vlabel)
    letters = [r for r in rows if r["channel"] == "letter"]
    pages = Counter()
    for r in letters:
        pages[r["commenter_type"]] += r["pages_total"] or 0
    put("A4", "Commenter type share (%)",
        {"voices": {k: share(U([r for r in rows if r["commenter_type"] == k]), Uall) for k in
                    ("resident", "organization", "developer_or_counsel", "government")},
         "letter_pages": {k: share(n, sum(pages.values())) for k, n in pages.most_common()}},
        "100·U(type=k)/U(V); 100·Σpages(type=k)/Σpages", vlabel)
    put("A5", "Non-English share (%)", {"all": share(U([r for r in rows if r["language"] != "en"]), Uall),
                                       **{l: share(U([r for r in rows if r["language"] == l]), Uall)
                                          for l in sorted({r["language"] for r in rows} - {"en"})}},
        "100·U(lang≠en)/U(V)", vlabel)
    pwv_tracts = [r["tract_id"] for r in pwv["rows"]]
    put("A6", "Residents in silent / problems-without-voice tracts (%)",
        {"silent": share(sum(pop[t] for t in silent), total_pop), "problems_without_voice": share(sum(pop[t] for t in pwv_tracts), total_pop)},
        "100·Σ_S pop/Σ pop", vlabel)
    dl = [r for r in rows if r["after_deadline"] is not None]
    put("A7", "After-deadline share (%)", share(sum(1 for r in dl if r["after_deadline"]), len(dl)) if dl else None,
        "100·|after|/|deadline known|", vlabel, note=None if dl else "deadline not recorded for any item")
    a8 = {}
    for c in P_cat:
        rates = [1000 * sum(p311["by_tract"].get(t, {}).get(c, {}).values()) / pop[t] * 12 / p311["months_covered"]
                 for t in p311["population"]]
        a8[clabel.get(c, c)] = {"median": r1(st.median(rates)), "max": r1(max(rates))}
    put("A8", "Category 311 rate per 1k per year (tract)", a8, "1000·P_t,c/pop(t)·12/M", "real")

    def net(rs):
        s_, o_ = U([r for r in rs if r["stance"] == "support"]), U([r for r in rs if r["stance"] == "oppose"])
        return None if not (s_ + o_) else round(100 * (s_ - o_) / (s_ + o_))
    put("A9", "Net support index (−100..+100)",
        {"by_category": {clabel[c]: net([r for r in rows if r["category"] == c]) for c in cats},
         "by_item": {k: {"net": net(v), "n_unique": r1(U(v), 1), "title": v[0]["item_title"][:70]} for k, v in items.items()}},
        "100·(U_sup−U_opp)/(U_sup+U_opp)", vlabel)
    g = vcity["gaps"]
    put("A10", "Representation ratio / participation gap",
        {"tracts_over_represented": sum(1 for x in g if x["observed"] > x["expected"]),
         "tracts_gap_1": sum(1 for x in g if x["gap"] == 1.0),
         "max_ratio": r1(max((x["observed"] / x["expected"]) for x in g if x["expected"]), 1)},
        "ratio=obs/exp; gap=(exp−obs)/exp", vlabel)
    h4, h5 = M["H4"]["value"], M["H5"]["value"]
    put("A11", "Attention gap by category (pp, 311 share − voice share)",
        {k: r1((h5.get(k) or 0) - (h4.get(k) or 0)) for k in h4}, "H5_c − H4_c", "mixed: 311 real, voice " + vlabel)
    lv = sorted(located_u.values(), reverse=True)
    top = max(1, round(0.1 * len(pop)))
    put("A12", "Voice concentration", {"top_10pct_tracts_share": share(sum(lv[:top]), sum(lv)),
                                       "gini_over_215_tracts": gini([located_u.get(t, 0) for t in pop])},
        "share of U(L) from top 10% of tracts; Gini", vlabel)
    put("A13", "Corrected weights (low_income)",
        {"aif360_reweighing": {k: r1(v["weight"], 3) for k, v in vcity["correct"]["reweighing"]["low_income"].items()},
         "population_weight_range": [r1(min(x for x in vcity["correct"]["population_weight"].values() if x), 3),
                                     r1(max(x for x in vcity["correct"]["population_weight"].values() if x), 3)],
         "population_weight_null_tracts": sum(1 for x in vcity["correct"]["population_weight"].values() if not x)},
        "W(g,l)=P(g)P(l)/P(g,l); w_t=(pop share)/(voice share)", vlabel)
    put("A14", "Underheard ranking (top 5)", vcity["underheard"][:5], "gap × relevance", vlabel)
    th = vcity["theme_rankings"]
    put("A15", "Theme ranking three ways (voice)",
        {w: [{"rank": x["rank"], "category": clabel.get(x["category"], x["category"]), "rank_change": x.get("rank_change", 0)}
             for x in th[w]] for w in ("raw", "aif360_reweighted", "population_reweighted")}, "rank by U, U·W, U·w_t", vlabel)
    put("A16", "311 category by volume", [{"category": x["label"], "count": int(x["score"]), "share": r1(100 * x["share"])}
                                         for x in pcity["category_volume"]], "P_c sorted", "real")
    months = Counter()
    for t, cs in p311["by_tract"].items():
        for c, m in cs.items():
            for k, n in m.items():
                months[k] += n
    ms = sorted(months)
    put("A17", "311 monthly trend", {"months": {m: months[m] for m in ms},
                                     "last_full_month_change_pct": share(months[ms[-2]] - months[ms[-3]], months[ms[-3]]),
                                     "partial_month": ms[-1]}, "Σ per month; 100·(x_m−x_{m−1})/x_{m−1}", "real")
    days = []
    for r in rows:
        if r["meeting_date"] and r["received_at"]:
            d = (date.fromisoformat(r["meeting_date"]) - datetime.fromisoformat(r["received_at"]).date()).days
            days.append((r["channel"], d))
    put("A18", "Comment timing (days before meeting)",
        {c: {"median_days": st.median([d for ch, d in days if ch == c]),
             "within_2_days_pct": share(sum(1 for ch, d in days if ch == c and 0 <= d <= 2), sum(1 for ch, _ in days if ch == c))}
         for c in sorted({c for c, _ in days})}, "meeting_date − received_at", vlabel)
    # A19 example region: tracts whose centroid is in council district 7 (Story/King, Tully)
    import geopandas as gpd
    tg = gpd.read_file(PUB / "tracts.geojson")
    dg = gpd.read_file(PUB / "council_districts.geojson")
    cent = tg.set_geometry(tg.to_crs(3310).centroid).to_crs(4326)
    d7 = gpd.sjoin(cent, dg[dg["district"] == 7], predicate="within")["tract_id"].tolist()
    city = FZ.load_real()
    reg = FZ.region_summary(d7, city)
    put("A19", "Region summary example: Council District 7", {"tracts": len(d7), "summary": reg},
        "fairness.region_summary(tracts in D7)", vlabel)

    # ------------------------------------------------------------------ Tier 3
    put("Q1", "Labeling engine share (%)", {k: share(n, len(rows)) for k, n in Counter(r["engine"] for r in rows).items()},
        "100·|engine=k|/|V|", "real")
    conf = [r["confidence"] for r in rows if r["confidence"] is not None]
    put("Q2", "Low-confidence share (%)", {"below_0.6": share(sum(1 for c in conf if c < 0.6), len(conf)),
                                          "below_0.8": share(sum(1 for c in conf if c < 0.8), len(conf)),
                                          "mean_confidence": r1(st.mean(conf), 3)}, "100·|conf<0.6|/|V|", "real")
    inh = [r for r in rows if r["inherited_from"]]
    put("Q3", "Inherited and aligned labels", {"inherited_pct": share(len(inh), len(rows)), "inherited": len(inh),
                                              "aligned": sum(1 for r in inh if str(r.get("quote_aligned")).lower() == "true")},
        "|inherited|/|V|; |aligned|/|inherited|", "real")
    L = [r for r in rows if r["tract_id"]]
    put("Q4", "Location quality mix (% of located)",
        {"source": {k: share(n, len(L)) for k, n in Counter(r["location_source"] for r in L).most_common()},
         "basis": {k: share(n, len(L)) for k, n in Counter(r["location_basis"] for r in L).most_common()},
         "multi_tract": share(sum(1 for r in L if r["multi_tract"]), len(L))}, "shares among L", vlabel)
    put("Q5", "OCR share of letters (%)", share(sum(1 for r in letters if r["ocr"]), len(letters)), "100·|ocr|/|letters|", "real")
    put("Q6", "Simulated share (%)", {"rows": share(sum(1 for r in rows if r["mock"]), len(rows)),
                                     "unique_voices": share(U([r for r in rows if r["mock"]]), Uall)}, "100·|mock|/|V|", "real")
    put("Q7", "311 coverage (%)", {"located": share(p311["rows_located"], p311["rows_total"]),
                                  "not_problems": share(p311["rows_not_problems"], p311["rows_total"]),
                                  "rows_total": p311["rows_total"]}, "rows_located/rows_total; rows_not_problems/rows_total", "real")
    cost = sum(float(r.get("session_costs") or 0) for r in runs)
    put("Q8", "Bob cost", {"total_usd": round(cost, 2), "per_comment_usd": round(cost / len(rows), 4), "runs": len(runs)},
        "Σ session_costs / |V|", "real")
    put("Q9", "Classifier audit agreement", None, "after human labels: 100·|pred=true|/|labeled|", "real",
        note="not yet audited: data/labeled_sample_template.csv has no human labels")
    flags = []
    if mock_any:
        flags.append("voice metrics are illustrative: simulated emails contribute")
    if not dl:
        flags.append("after-deadline share unavailable: no comment deadlines recorded")
    if reg.get("not_enough_data"):
        flags.append("District 7 region fairness: not enough data")
    flags.append(f"311 month {ms[-1]} is partial")
    put("Q10", "Validity flags", flags, "see docs/METRICS.md Q10", "real")

    OUT.write_text(json.dumps({"generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                               "scope": "citywide, all items, no filters", "metrics": M}, indent=1, ensure_ascii=False,
                              allow_nan=False, default=str))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(M)} metrics")
    return 0


if __name__ == "__main__":
    sys.exit(main())
