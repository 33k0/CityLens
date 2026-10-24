#!/usr/bin/env python3
"""Steps f/g: fairness metrics, per family, never blended.

Families (scripts/families.py): Voice = letters + email + site, Problems = 311. Every number below is computed
inside one family. The only cross-family view is problems_without_voice on citywide percentiles of per-1k rates.

Unit of analysis is the census tract (215 San Jose tracts in data/tracts.csv). Per tract and family:
  rate_per_1k      families.rate_per_1k (311 annualized via months_covered; voice is per 1k over the corpus window)
  favorable        rate > city_median_rate_per_1k, the median over all 215 tracts, computed ONCE and stored
Protected attributes are binary, 1 = privileged (group expected to be over-represented), 0 = unprivileged.
DI = P(fav | unpriv) / P(fav | priv); SPD = P(fav | unpriv) - P(fav | priv). Computed with AIF360
(BinaryLabelDataset + BinaryLabelDatasetMetric) and cross-checked with pandas to 1e-9, unweighted (each tract one
unit) and population-weighted (instance_weights = population; AIF360's base rates sum instance weights).

Usage:  python scripts/fairness.py            # real data -> public/data/fairness/*.json
        python scripts/fairness.py --demo     # synthetic tracts, prints metrics, writes nothing
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import MappingProxyType

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import families as fam  # noqa: E402

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)  # AIF360 logs optional-dependency warnings at import
import aif360  # noqa: E402
from aif360.algorithms.preprocessing import Reweighing  # noqa: E402
from aif360.datasets import BinaryLabelDataset  # noqa: E402
from aif360.metrics import BinaryLabelDatasetMetric  # noqa: E402

logging.disable(logging.NOTSET)

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"
PUB = ROOT / "public" / "data"
OUT = PUB / "fairness"
TOL = 1e-9

DEFAULT_ATTR = "low_income"
ATTRIBUTES = {
    "low_income": {"column": "median_income", "unprivileged": "median_income < city median of tract median incomes",
                   "privileged": "median_income >= that median"},
    "majority_nonwhite": {"column": "pct_nonwhite", "unprivileged": "pct_nonwhite > 0.5", "privileged": "pct_nonwhite <= 0.5"},
    "renter_majority": {"column": "pct_renter", "unprivileged": "pct_renter > 0.5", "privileged": "pct_renter <= 0.5"},
    "high_lep": {"column": "pct_lep", "unprivileged": "pct_lep > 75th percentile of tracts (pandas quantile, linear)",
                 "privileged": "pct_lep <= that threshold"},
}
OUTCOME = {"voice": "comment participation above median", "problems": "311 reporting above median"}
BANNED_WORDS = ["unfair", "biased", "apathetic"]
CHANNELS_GENERIC = ["multilingual mailer", "community meeting at a nearby library/community center", "door-hanger",
                    "partner with local organizations"]
WORDING_RULES = {
    "banned_words": BANNED_WORDS,
    "rules": ["facts only: population, renter share, LEP share, observed vs expected comments, 311 percentile",
              "never describe what residents of a tract with few comments think or want",
              "never name specific organizations; outreach channels are generic",
              "never present a blended voice + 311 number"],
    "channels": CHANNELS_GENERIC,
}
RELEVANCE_INSIDE, RELEVANCE_OUTSIDE = 1.0, 0.25
MIN_REGION_TRACTS, MIN_GROUP_TRACTS, MIN_REGION_VOICE = 5, 2, 10
TOP_K = 5
RESIDENCE_BASES = ("residence", "both")
MIN_RESIDENCE_ROWS = 30


def attach_location_basis(comments: list[dict], locations_csv: Path | None = None) -> list[dict]:
    """location_basis in {residence, issue, both}; taken from comments.json, else data/locations.csv by comment_id,
    else 'unknown'."""
    lookup = {}
    if locations_csv is not None and locations_csv.exists():
        loc = pd.read_csv(locations_csv, dtype=str, keep_default_na=False)
        if "location_basis" in loc.columns:
            lookup = dict(zip(loc["comment_id"], loc["location_basis"].str.strip().str.lower()))
    out = []
    for c in comments:
        b = (c.get("location_basis") or lookup.get(c.get("comment_id"), "") or "").strip().lower()
        out.append({**c, "location_basis": (b or "unknown") if c.get("tract_id") else None})
    return out


def participation_basis(comments: list[dict]) -> tuple[str, list[dict], dict]:
    """Who is heard: by default only rows located by the writer's residence (basis residence|both); falls back to
    all located rows when fewer than MIN_RESIDENCE_ROWS voice rows have a residence basis. Returns (basis used,
    participation rows with non-residence tract_ids blanked, counts)."""
    located = [c for c in comments if c.get("tract_id")]
    res = [c for c in located if c.get("location_basis") in RESIDENCE_BASES]
    counts = {"located_rows": len(located), "residence_rows": len(res),
              "by_basis": {b: sum(1 for c in located if c.get("location_basis") == b) for b in sorted({c.get("location_basis") for c in located})},
              "min_residence_rows": MIN_RESIDENCE_ROWS}
    if len(res) >= MIN_RESIDENCE_ROWS:
        return "residence", [c if c.get("location_basis") in RESIDENCE_BASES else {**c, "tract_id": None} for c in comments], counts
    return "all_located", list(comments), counts


# ----------------------------------------------------------------------------------------------- attributes
def attribute_groups(tracts: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """1 = privileged, 0 = unprivileged. Returns (frame indexed by tract_id, thresholds used)."""
    th = {"low_income": float(tracts["median_income"].median()), "majority_nonwhite": 0.5, "renter_majority": 0.5,
          "high_lep": float(tracts["pct_lep"].quantile(0.75))}
    g = pd.DataFrame(index=tracts["tract_id"].values)
    g["low_income"] = (tracts["median_income"].values >= th["low_income"]).astype(int)
    g["majority_nonwhite"] = (tracts["pct_nonwhite"].values <= th["majority_nonwhite"]).astype(int)
    g["renter_majority"] = (tracts["pct_renter"].values <= th["renter_majority"]).astype(int)
    g["high_lep"] = (tracts["pct_lep"].values <= th["high_lep"]).astype(int)
    return g, th


# ----------------------------------------------------------------------------------------------- metrics
def _pandas_rates(units: pd.DataFrame, attr: str, weight_col: str | None) -> dict:
    w = units[weight_col].astype(float) if weight_col else pd.Series(1.0, index=units.index)
    out = {}
    for name, val in (("privileged", 1), ("unprivileged", 0)):
        m = units[attr] == val
        wsum = float(w[m].sum())
        wfav = float((w[m] * units.loc[m, "favorable"]).sum())
        out[name] = {"n": int(m.sum()), "favorable": int(units.loc[m, "favorable"].sum()),
                     "weight": wsum, "weight_favorable": wfav, "base_rate": (wfav / wsum) if wsum > 0 else None}
    p, u = out["privileged"]["base_rate"], out["unprivileged"]["base_rate"]
    out["spd"] = (u - p) if p is not None and u is not None else None
    out["di"] = (u / p) if p not in (None, 0) and u is not None else None
    return out


def _aif360(units: pd.DataFrame, attr: str, weight_col: str | None) -> dict:
    df = units[[attr, "favorable"]].astype(float).copy()
    df["w"] = units[weight_col].astype(float).values if weight_col else 1.0
    ds = BinaryLabelDataset(df=df, label_names=["favorable"], protected_attribute_names=[attr], favorable_label=1.0,
                            unfavorable_label=0.0, instance_weights_name="w")
    m = BinaryLabelDatasetMetric(ds, unprivileged_groups=[{attr: 0}], privileged_groups=[{attr: 1}])
    with np.errstate(all="ignore"):
        di, spd = float(m.disparate_impact()), float(m.statistical_parity_difference())
    clean = lambda v: None if (v is None or not np.isfinite(v)) else v
    return {"di": clean(di), "spd": clean(spd)}


def _close(a, b) -> bool:
    return (a is None and b is None) or (a is not None and b is not None and abs(a - b) <= TOL)


def measure(units: pd.DataFrame, attr: str = DEFAULT_ATTR, weighted: bool = False) -> dict:
    """DI/SPD for one family on tract units (columns: favorable, population, attr). AIF360 is the source of record;
    pandas must agree to 1e-9 or this raises."""
    units = units.dropna(subset=[attr, "favorable"])
    wc = "population" if weighted else None
    pd_res = _pandas_rates(units, attr, wc)
    out = {"attribute": attr, "weighting": "population" if weighted else "none (each tract one unit)",
           "privileged": pd_res["privileged"], "unprivileged": pd_res["unprivileged"]}
    if pd_res["privileged"]["n"] == 0 or pd_res["unprivileged"]["n"] == 0:
        return {**out, "di": None, "spd": None, "aif360": None, "pandas": {"di": pd_res["di"], "spd": pd_res["spd"]},
                "note": "one group is empty"}
    a = _aif360(units, attr, wc)
    if not (_close(a["di"], pd_res["di"]) and _close(a["spd"], pd_res["spd"])):
        raise AssertionError(f"AIF360 vs pandas mismatch for {attr} weighted={weighted}: {a} vs {pd_res}")
    return {**out, "di": a["di"], "spd": a["spd"], "aif360": a, "pandas": {"di": pd_res["di"], "spd": pd_res["spd"]},
            "crosscheck_tolerance": TOL}


def measure_all(units: pd.DataFrame, attrs=ATTRIBUTES) -> dict:
    return {a: {"unweighted": measure(units, a, False), "population_weighted": measure(units, a, True)} for a in attrs}


# ----------------------------------------------------------------------------------------------- correction
def reweighing_weights(units: pd.DataFrame, attr: str) -> tuple[dict, pd.Series]:
    """AIF360 Reweighing: W(g,l) = P(g)P(l)/P(g,l). Returns (cell table, per-tract weight)."""
    df = units[[attr, "favorable"]].astype(float).copy()
    ds = BinaryLabelDataset(df=df, label_names=["favorable"], protected_attribute_names=[attr], favorable_label=1.0,
                            unfavorable_label=0.0)
    rw = Reweighing(unprivileged_groups=[{attr: 0}], privileged_groups=[{attr: 1}]).fit(ds)
    tw = pd.Series(rw.transform(ds).instance_weights, index=units.index)
    cells = {}
    for gname, g in (("privileged", 1), ("unprivileged", 0)):
        for lname, lab in (("favorable", 1), ("unfavorable", 0)):
            m = (units[attr] == g) & (units["favorable"] == lab)
            n, ng, nl, N = int(m.sum()), int((units[attr] == g).sum()), int((units["favorable"] == lab).sum()), len(units)
            expect = (ng * nl / (N * n)) if n else None
            got = float(tw[m].iloc[0]) if n else None
            if n and abs(got - expect) > TOL:
                raise AssertionError(f"Reweighing cell mismatch {attr} {gname}/{lname}: {got} vs {expect}")
            cells[f"{gname}|{lname}"] = {"n_tracts": n, "weight": got}
    return cells, tw


def correct(units: pd.DataFrame, family: str, voice_counts: pd.Series | None = None, attrs=ATTRIBUTES) -> dict:
    """Reweighing weights per (group, label) cell for every attribute; for voice also the population-share weight
    per tract = population_share / comment_share (null where a tract has no located comments)."""
    out = {"reweighing": {}, "reweighing_tract_weights": {}}
    for a in attrs:
        cells, tw = reweighing_weights(units, a)
        out["reweighing"][a] = cells
        out["reweighing_tract_weights"][a] = {t: round(float(v), 12) for t, v in tw.items()}
    if family == "voice" and voice_counts is not None:
        out["population_weight"] = {t: (None if v is None else round(v, 12)) for t, v in population_weights(units, voice_counts).items()}
    return out


def population_weights(units: pd.DataFrame, counts: pd.Series) -> dict:
    pop_share = units["population"] / units["population"].sum()
    c = counts.reindex(units.index).fillna(0.0)
    total = c.sum()
    out = {}
    for t in units.index:
        out[t] = float(pop_share[t] / (c[t] / total)) if total > 0 and c[t] > 0 else None
    return out


# ----------------------------------------------------------------------------------------------- voice counting
def voice_row_weights(comments: list[dict], mode: str = "dedup") -> list[float]:
    """dedup (default): duplicate_of rows count 0; each campaign_id counts once citywide, split evenly over its
    non-duplicate rows (so a campaign is one voice in total, spread over the tracts its senders are in); others 1.
    raw: every row counts 1."""
    if mode == "raw":
        return [1.0] * len(comments)
    sizes: dict[str, int] = {}
    for c in comments:
        if c.get("campaign_id") and not c.get("duplicate_of"):
            sizes[c["campaign_id"]] = sizes.get(c["campaign_id"], 0) + 1
    out = []
    for c in comments:
        if c.get("duplicate_of"):
            out.append(0.0)
        elif c.get("campaign_id"):
            out.append(1.0 / sizes[c["campaign_id"]])
        else:
            out.append(1.0)
    return out


def check_voice(comments: list[dict]) -> None:
    for c in comments:
        if fam.FAMILY_OF.get(c.get("channel")) != "voice":
            raise ValueError(f"channel separation: a {c.get('channel')!r} row cannot enter the voice family")


def voice_counts(comments: list[dict], tract_ids, mode: str = "dedup") -> dict:
    check_voice(comments)
    w = voice_row_weights(comments, mode)
    by_tract = pd.Series(0.0, index=list(tract_ids))
    by_channel: dict[str, float] = {}
    located = unlocated = 0.0
    for c, wi in zip(comments, w):
        by_channel[c["channel"]] = by_channel.get(c["channel"], 0.0) + wi
        t = c.get("tract_id")
        if t and t in by_tract.index:
            by_tract[t] += wi
            located += wi
        else:
            unlocated += wi
    return {"by_tract": by_tract, "total": located + unlocated, "located": located, "unlocated": unlocated,
            "by_channel": by_channel, "rows": len(comments)}


# ----------------------------------------------------------------------------------------------- city context
@dataclass
class City:
    tracts: pd.DataFrame                    # indexed by tract_id: population, demographics, attribute flags
    thresholds: dict
    comments: list[dict]
    voice_by_tract: pd.Series               # dedup counts
    problems_by_tract: pd.Series            # 311 totals
    problems_by_cat: dict                   # tract -> {category: count}
    months_covered: int
    problems_meta: dict = field(default_factory=dict)  # category_labels, taxonomy_source, rows_not_problems
    rates: dict = field(default_factory=dict)       # family -> Series
    medians: MappingProxyType = None                # family -> float, computed once
    median_computations: int = 0
    region_comments: list[dict] | None = None      # rows used for region/map counts (all located); None = comments
    location_basis: dict = field(default_factory=dict)

    def units(self, family: str) -> pd.DataFrame:
        u = self.tracts[["population", *ATTRIBUTES]].copy()
        u["rate"] = self.rates[family]
        u["favorable"] = (u["rate"] > self.medians[family]).astype(int)
        return u


def build_city(tracts: pd.DataFrame, comments: list[dict], problems_totals: dict, problems_by_cat: dict, months_covered: int) -> City:
    tracts = tracts.copy()
    tracts["tract_id"] = tracts["tract_id"].astype(str)
    groups, th = attribute_groups(tracts)
    t = tracts.set_index("tract_id").join(groups)
    check_voice(comments)
    vc = voice_counts(comments, t.index)["by_tract"]
    pc = pd.Series({k: float(problems_totals.get(k, 0)) for k in t.index})
    city = City(tracts=t, thresholds=th, comments=comments, voice_by_tract=vc, problems_by_tract=pc,
                problems_by_cat=problems_by_cat, months_covered=months_covered)
    city.rates = {"voice": pd.Series({k: fam.rate_per_1k(vc[k], t.at[k, "population"]) for k in t.index}),
                  "problems": pd.Series({k: fam.rate_per_1k(pc[k], t.at[k, "population"], months_covered) for k in t.index})}
    city.medians = MappingProxyType({f: float(city.rates[f].dropna().median()) for f in ("voice", "problems")})
    city.median_computations = 1
    return city


# ----------------------------------------------------------------------------------------------- region
def region_summary(tract_ids, city: City, attr: str = DEFAULT_ATTR, voice_comments: list[dict] | None = None,
                   problem_rows: list[dict] | None = None) -> dict:
    """Region view for a set of tracts. Families stay under separate keys; outcomes use the CITYWIDE median.
    voice_comments / problem_rows may override the city's rows (each must be single-family or this raises)."""
    ids = [t for t in dict.fromkeys(str(x) for x in tract_ids) if t in city.tracts.index]
    if voice_comments is None:
        comments = city.region_comments if city.region_comments is not None else city.comments
    else:
        comments = voice_comments
    check_voice(comments)
    if problem_rows is not None:
        fam.sum_within_family("problems", problem_rows)
    sel = set(ids)
    reg_comments = [c for c in comments if c.get("tract_id") in sel]
    vc = voice_counts(reg_comments, ids)
    vc_raw = voice_counts(reg_comments, ids, "raw")
    p_count = float(city.problems_by_tract.reindex(ids).fillna(0).sum()) if problem_rows is None else float(
        fam.sum_within_family("problems", [r for r in problem_rows if r.get("tract_id") in sel]))
    u = city.tracts.loc[ids]
    n_priv, n_unpriv = int((u[attr] == 1).sum()), int((u[attr] == 0).sum())
    counts = {"n_tracts": len(ids), "groups": {"privileged": n_priv, "unprivileged": n_unpriv},
              "voice": {"count": round(vc["total"], 9), "count_raw": vc_raw["total"],
                        "by_channel": {k: round(v, 9) for k, v in vc["by_channel"].items()}},
              "requests_311": {"count": p_count}}
    base = {"attribute": attr, "city_median_rate_per_1k": dict(city.medians), "counts": counts}
    reasons = []
    if len(ids) < MIN_REGION_TRACTS:
        reasons.append(f"fewer than {MIN_REGION_TRACTS} tracts")
    if n_priv < MIN_GROUP_TRACTS or n_unpriv < MIN_GROUP_TRACTS:
        reasons.append(f"a group has fewer than {MIN_GROUP_TRACTS} tracts")
    if vc["total"] < MIN_REGION_VOICE:
        reasons.append(f"fewer than {MIN_REGION_VOICE} voice comments")
    if reasons:
        return {**base, "not_enough_data": True, "reasons": reasons}

    # category shares, each within its own family
    w = voice_row_weights(comments)
    wmap = {id(c): wi for c, wi in zip(comments, w)}
    vcat: dict[str, float] = {}
    for c in reg_comments:
        vcat[c.get("category") or "unclassified"] = vcat.get(c.get("category") or "unclassified", 0.0) + wmap[id(c)]
    vt = sum(vcat.values())
    pcat: dict[str, float] = {}
    for t in ids:
        for k, v in (city.problems_by_cat.get(t) or {}).items():
            pcat[k] = pcat.get(k, 0.0) + v
    pt = fam.sum_within_family("problems", [{"channel": "311", "n": v} for v in pcat.values()])
    out = {**base, "not_enough_data": False}
    for key, fname, shares in (("voice", "voice", {k: v / vt for k, v in vcat.items()} if vt else {}),
                               ("requests_311", "problems", {k: v / pt for k, v in pcat.items()} if pt else {})):
        units = city.units(fname).loc[ids]
        out[key] = {"family": fname, "outcome": OUTCOME[fname], "count": counts[key]["count"],
                    "category_shares": dict(sorted(shares.items(), key=lambda kv: -kv[1])),
                    "unweighted": measure(units, attr, False), "population_weighted": measure(units, attr, True)}
    return out


# ----------------------------------------------------------------------------------------------- audit pieces
def load_taxonomy(path: Path | None = None) -> dict:
    """Voice category keys come only from data/categories.json (never hard-coded here)."""
    path = path or (D / "categories.json")
    if not path.exists():
        return {"keys": [], "authored_by": None, "version": None, "categories_source": "missing"}
    raw = json.loads(path.read_text())
    cats = raw.get("categories", raw) if isinstance(raw, dict) else raw
    by = raw.get("authored_by") if isinstance(raw, dict) else None
    return {"keys": [c["key"] for c in cats], "labels": {c["key"]: c.get("label", c["key"]) for c in cats},
            "authored_by": by, "version": raw.get("version") if isinstance(raw, dict) else None,
            "categories_source": "ibm-bob" if by == "ibm-bob" else f"{by or 'unknown'} fallback"}


def rank_table(scores: dict) -> list[dict]:
    items = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"category": k, "score": round(v, 9), "rank": i + 1} for i, (k, v) in enumerate(items)]


def theme_rankings(city: City, attr: str, rw_tract: pd.Series, pop_w: dict, taxonomy: dict | None = None) -> dict:
    """Voice only. All three on located comments (the only ones a tract weight can apply to); raw over every
    comment is reported separately."""
    w = voice_row_weights(city.comments)
    keys = (taxonomy or {}).get("keys") or []
    raw_all, raw, rwc, popc = ({k: 0.0 for k in keys} for _ in range(4))
    for c, wi in zip(city.comments, w):
        k = c.get("category") or "unclassified"
        raw_all[k] = raw_all.get(k, 0.0) + wi
        t = c.get("tract_id")
        if not t or t not in city.tracts.index:
            continue
        raw[k] = raw.get(k, 0.0) + wi
        rwc[k] = rwc.get(k, 0.0) + wi * float(rw_tract[t])
        popc[k] = popc.get(k, 0.0) + wi * float(pop_w[t] or 0.0)
    tabs = {"raw": rank_table(raw), "aif360_reweighted": rank_table(rwc), "population_reweighted": rank_table(popc)}
    base = {r["category"]: r["rank"] for r in tabs["raw"]}
    for name in ("aif360_reweighted", "population_reweighted"):
        for r in tabs[name]:
            r["rank_change"] = base[r["category"]] - r["rank"]  # positive = moved up vs raw
    known = set(keys)
    off = sorted({k for k in raw_all if keys and k not in known and k != "unclassified"})
    return {"attribute": attr, "basis": "located comments, one voice per person/campaign",
            "categories_source": (taxonomy or {}).get("categories_source"), "taxonomy_version": (taxonomy or {}).get("version"),
            "labels": (taxonomy or {}).get("labels", {}), "keys_not_in_taxonomy": off, **tabs,
            "raw_all_comments": rank_table(raw_all)}


def participation_gaps(units: pd.DataFrame, counts: pd.Series) -> pd.DataFrame:
    total = float(counts.reindex(units.index).fillna(0).sum())
    share = units["population"] / units["population"].sum()
    g = pd.DataFrame({"population_share": share, "observed": counts.reindex(units.index).fillna(0.0)})
    g["expected"] = share * total
    g["gap"] = np.where(g["expected"] > 0, (g["expected"] - g["observed"]) / g["expected"], np.nan)
    return g


def load_affected(items: list[str]) -> dict:
    p = PUB / "affected.json"
    cur = json.loads(p.read_text()) if p.exists() else {}
    cur.setdefault("_note", "Staff-editable. affected_tracts: tract_ids that an item affects (relevance 1.0; others 0.25). "
                            "Empty list with default 'all' = citywide (every tract relevance 1.0).")
    cur.setdefault("items", {})
    changed = not p.exists()
    for it in items:
        if it not in cur["items"]:
            cur["items"][it] = {"affected_tracts": [], "default": "all"}
            changed = True
    if changed:
        p.write_text(json.dumps(cur, indent=1))
    return cur


def relevance(tract: str, spec: dict | None) -> float:
    if not spec or (not spec.get("affected_tracts") and spec.get("default", "all") == "all"):
        return RELEVANCE_INSIDE
    return RELEVANCE_INSIDE if tract in set(spec.get("affected_tracts") or []) else RELEVANCE_OUTSIDE


def underheard(gaps: pd.DataFrame, spec: dict | None = None, k: int = TOP_K) -> list[dict]:
    rows = []
    for t, r in gaps.iterrows():
        if pd.isna(r["gap"]):
            continue
        rel = relevance(t, spec)
        rows.append({"tract_id": t, "gap": float(r["gap"]), "relevance": rel, "score": float(r["gap"]) * rel,
                     "observed": float(r["observed"]), "expected": float(r["expected"])})
    rows.sort(key=lambda x: (-x["score"], -x["expected"], x["tract_id"]))
    return rows[:k]


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def brief(t: str, city: City, row: dict, problems_pct: dict) -> dict:
    tr = city.tracts.loc[t]
    renter, lep = float(tr["pct_renter"]), float(tr["pct_lep"])
    channels = []
    if lep > city.thresholds["high_lep"]:
        channels.append("multilingual mailer")
    if renter > 0.5:
        channels.append("door-hanger")
    channels.append("community meeting at a nearby library/community center")
    channels.append("partner with local organizations")
    if "multilingual mailer" not in channels and lep >= 0.10:
        channels.insert(0, "multilingual mailer")
    pp = problems_pct.get(t)
    facts = {"population": int(tr["population"]), "renter_share": round(renter, 4), "lep_share": round(lep, 4),
             "observed_comments": round(row["observed"], 2), "expected_comments": round(row["expected"], 2),
             "problems_311_percentile": None if pp is None else round(pp, 1)}
    text = (f"Tract {t}: {facts['population']:,} residents; {renter * 100:.0f}% renters; "
            f"{lep * 100:.0f}% limited-English-proficiency. Located comments: {row['observed']:.1f} observed vs "
            f"{row['expected']:.1f} expected from its population share. 311 reporting per 1k residents: "
            + ("n/a" if pp is None else f"{ordinal(int(round(pp)))} citywide percentile") + ". Suggested outreach: " + "; ".join(channels) + ".")
    for w in BANNED_WORDS:
        assert w not in text.lower(), w
    return {"tract_id": t, "facts": facts, "channels": channels, "text": text, "template": "outreach-v1"}


def category_volume_311(city: City) -> list[dict]:
    tot: dict[str, float] = {}
    for t in city.tracts.index:
        for k, v in (city.problems_by_cat.get(t) or {}).items():
            tot[k] = tot.get(k, 0.0) + v
    grand = fam.sum_within_family("problems", [{"channel": "311", "n": v} for v in tot.values()])
    lab = city.problems_meta.get("category_labels") or {}
    return [{**r, "label": lab.get(r["category"], r["category"]), "share": r["score"] / grand if grand else None} for r in rank_table(tot)]


def labels(city: City, family: str) -> dict:
    if family == "problems":
        return {"family": "problems", "real": True, "label": "real", "channels": {"311": float(city.problems_by_tract.sum())}}
    vc = voice_counts(city.comments, city.tracts.index)
    raw = voice_counts(city.comments, city.tracts.index, "raw")
    mock = any(c.get("mock") for c in city.comments)
    return {"family": "voice", "real": not mock, "label": "illustrative" if mock else "real",
            "label_reason": "includes simulated emails (mock=true)" if mock else None,
            "channels": {k: {"count": round(v, 9), "rows": raw["by_channel"].get(k, 0)} for k, v in vc["by_channel"].items()},
            "totals": {"count": round(vc["total"], 9), "located": round(vc["located"], 9), "unlocated": round(vc["unlocated"], 9),
                       "rows": vc["rows"]}}


def audit(city: City, family: str, attr: str = DEFAULT_ATTR, affected: dict | None = None, taxonomy: dict | None = None) -> dict:
    units = city.units(family)
    out = {**labels(city, family), "outcome": OUTCOME[family], "attribute_default": attr,
           "city_median_rate_per_1k": city.medians[family], "thresholds": city.thresholds}
    if family == "voice" and voice_counts(city.comments, city.tracts.index)["located"] == 0:
        return {**out, "status": "pending_locations", "note": "no voice comment has a tract_id yet"}
    out["status"] = "ok"
    out["measure"] = measure_all(units)
    pct = {f: fam.percentile_ranks({t: (None if pd.isna(v) else float(v)) for t, v in city.rates[f].items()}) for f in ("voice", "problems")}
    if family == "problems":
        out["correct"] = correct(units, "problems")
        out["category_volume"] = category_volume_311(city)
        out["taxonomy_source"] = city.problems_meta.get("taxonomy_source")
        out["rows_not_problems"] = city.problems_meta.get("rows_not_problems")
        out["rates_basis"] = "problem reports only (requests Bob mapped to 'none' are excluded from totals and rates)"
        out["tracts"] = [{"tract_id": t, "population": int(units.at[t, "population"]), "count": float(city.problems_by_tract[t]),
                          "rate_per_1k": round(float(units.at[t, "rate"]), 6), "favorable": int(units.at[t, "favorable"]),
                          "percentile": pct["problems"][t], "groups": {a: int(units.at[t, a]) for a in ATTRIBUTES}} for t in units.index]
        return out

    # voice
    raw_counts = voice_counts(city.comments, city.tracts.index, "raw")["by_tract"]
    ru = units.copy()
    ru["rate"] = [fam.rate_per_1k(raw_counts[t], ru.at[t, "population"]) for t in ru.index]
    raw_median = float(ru["rate"].median())
    ru["favorable"] = (ru["rate"] > raw_median).astype(int)
    out["measure_raw_counts"] = {"city_median_rate_per_1k": raw_median, "measure": measure_all(ru)}
    letters = [c for c in city.comments if c["channel"] == "letter"]
    if letters:
        lc = voice_counts(letters, city.tracts.index)["by_tract"]
        lu = units.copy()
        lu["rate"] = [fam.rate_per_1k(lc[t], lu.at[t, "population"]) for t in lu.index]
        lm = float(lu["rate"].median())
        lu["favorable"] = (lu["rate"] > lm).astype(int)
        out["measure_letters_only"] = {"real": True, "label": "real (letters only)", "city_median_rate_per_1k": lm,
                                       "located": float(lc.sum()), "measure": measure_all(lu)}
    cor = correct(units, "voice", city.voice_by_tract)
    out["correct"] = cor
    _, rw_tract = reweighing_weights(units, attr)
    out["theme_rankings"] = theme_rankings(city, attr, rw_tract, cor["population_weight"], taxonomy)
    gaps = participation_gaps(units, city.voice_by_tract)
    out["gaps"] = [{"tract_id": t, "population_share": round(r.population_share, 12), "observed": round(r.observed, 9),
                    "expected": round(r.expected, 9), "gap": None if pd.isna(r.gap) else round(r.gap, 9)} for t, r in gaps.iterrows()]
    ub = underheard(gaps)
    out["underheard"] = ub
    out["briefs"] = [brief(r["tract_id"], city, r, pct["problems"]) for r in ub]
    # per item
    affected = affected or {"items": {}}
    per_item = {}
    w = voice_row_weights(city.comments)
    items = sorted({c["item"] for c in city.comments})
    for it in items:
        cnt = pd.Series(0.0, index=city.tracts.index)
        for c, wi in zip(city.comments, w):
            if c["item"] == it and c.get("tract_id") in cnt.index:
                cnt[c["tract_id"]] += wi
        mock = any(c.get("mock") for c in city.comments if c["item"] == it)
        if cnt.sum() <= 0:
            per_item[it] = {"status": "no_located_comments", "real": not mock}
            continue
        spec = affected["items"].get(it)
        ig = participation_gaps(units, cnt)
        top = underheard(ig, spec)
        per_item[it] = {"status": "ok", "real": not mock, "label": "illustrative" if mock else "real",
                        "located": round(float(cnt.sum()), 9), "affected": spec or {"affected_tracts": [], "default": "all"},
                        "underheard": top, "briefs": [brief(r["tract_id"], city, r, pct["problems"]) for r in top]}
    out["per_item"] = per_item
    out["tracts"] = [{"tract_id": t, "population": int(units.at[t, "population"]), "count": round(float(city.voice_by_tract[t]), 9),
                      "count_raw": float(raw_counts[t]), "rate_per_1k": round(float(units.at[t, "rate"]), 9),
                      "favorable": int(units.at[t, "favorable"]), "percentile": pct["voice"][t],
                      "groups": {a: int(units.at[t, a]) for a in ATTRIBUTES}} for t in units.index]
    return out


def problems_without_voice_export(city: City) -> dict:
    pct = {f: fam.percentile_ranks({t: (None if pd.isna(v) else float(v)) for t, v in city.rates[f].items()}) for f in ("voice", "problems")}
    rows = fam.problems_without_voice(pct["problems"], pct["voice"])
    zero = sorted({t for t in city.tracts.index if city.voice_by_tract[t] == 0})
    mock = any(c.get("mock") for c in city.comments)
    return {"rule": f"problem_pct >= {fam.PROBLEM_PCT_MIN} and voice_pct <= {fam.VOICE_PCT_MAX} (citywide percentiles of "
                    "per-1k rates = share of tracts with a strictly lower rate, so tied zero-comment tracts score 0)",
            "real": not mock, "label": "illustrative" if mock else "real", "families": ["problems", "voice"],
            "note": "Percentiles only; voice and 311 counts are never combined.",
            "rows": rows, "zero_voice_tracts": len(zero)}


# ----------------------------------------------------------------------------------------------- parity fixtures
def synthetic(seed: int = 7, n: int = 40) -> tuple[pd.DataFrame, list[dict], dict, dict]:
    rng = np.random.default_rng(seed)
    tracts = pd.DataFrame({
        "tract_id": [f"s{i:03d}" for i in range(n)],
        "population": rng.integers(1500, 9000, n),
        "median_income": rng.integers(40000, 220000, n),
        "pct_renter": np.round(rng.uniform(0.1, 0.95, n), 4),
        "pct_nonwhite": np.round(rng.uniform(0.2, 0.99, n), 4),
        "pct_lep": np.round(rng.uniform(0.0, 0.4, n), 4)})
    comments, cats = [], ["theme_a", "theme_b", "theme_c", "theme_d"]
    for i, t in enumerate(tracts["tract_id"]):
        rich = tracts.at[i, "median_income"] > 130000
        k = int(rng.poisson(6 if rich else 2))
        for j in range(k):
            comments.append({"comment_id": f"c{i}_{j}", "tract_id": t, "channel": "letter" if j % 3 else "email",
                             "mock": j % 3 == 0, "item": "S-1" if j % 2 else "S-2", "category": cats[int(rng.integers(0, 4))],
                             "duplicate_of": None, "campaign_id": None})
    comments += [{"comment_id": "u1", "tract_id": None, "channel": "letter", "mock": False, "item": "S-1", "category": "theme_d",
                  "duplicate_of": None, "campaign_id": None}]
    for j in range(4):
        comments.append({"comment_id": f"camp{j}", "tract_id": "s001", "channel": "letter", "mock": False, "item": "S-2",
                         "category": "theme_a", "duplicate_of": "camp0" if j == 3 else None, "campaign_id": "CX"})
    totals = {t: int(rng.poisson(300 if inc < 130000 else 150) * pop / 4000)
              for t, pop, inc in zip(tracts["tract_id"], tracts["population"], tracts["median_income"])}
    by_cat = {t: {"problem_x": v // 2, "problem_y": v - v // 2} for t, v in totals.items()}
    return tracts, comments, totals, by_cat


def parity_fixtures() -> dict:
    tracts, comments, totals, by_cat = synthetic()
    city = build_city(tracts, comments, totals, by_cat, 12)
    rows = []
    for t in city.tracts.index:
        rows.append({"tract_id": t, "population": int(city.tracts.at[t, "population"]),
                     "voice_count": round(float(city.voice_by_tract[t]), 12), "problems_count": float(city.problems_by_tract[t]),
                     "voice_rate": float(city.rates["voice"][t]), "problems_rate": float(city.rates["problems"][t]),
                     **{a: int(city.tracts.at[t, a]) for a in ATTRIBUTES}})
    expected = {}
    for f in ("voice", "problems"):
        u = city.units(f)
        expected[f] = {a: {k: {"di": m["di"], "spd": m["spd"], "privileged": {"n": m["privileged"]["n"], "favorable": m["privileged"]["favorable"]},
                                "unprivileged": {"n": m["unprivileged"]["n"], "favorable": m["unprivileged"]["favorable"]}}
                           for k, m in res.items()} for a, res in measure_all(u).items()}
    ids = list(city.tracts.index)
    regions = []
    for name, sel in [("all", ids), ("first_half", ids[:20]), ("tiny", ids[:4]), ("low_voice", [t for t in ids if city.voice_by_tract[t] < 1][:8])]:
        r = region_summary(sel, city)
        e = {"name": name, "tract_ids": sel, "attr": DEFAULT_ATTR, "not_enough_data": r["not_enough_data"]}
        if not r["not_enough_data"]:
            e["voice"] = {k: {"di": r["voice"][k]["di"], "spd": r["voice"][k]["spd"]} for k in ("unweighted", "population_weighted")}
            e["requests_311"] = {k: {"di": r["requests_311"][k]["di"], "spd": r["requests_311"][k]["spd"]} for k in ("unweighted", "population_weighted")}
        regions.append(e)
    g = participation_gaps(city.units("voice"), city.voice_by_tract)
    return {"generator": "scripts/fairness.py synthetic(seed=7, n=40)", "aif360_version": aif360.__version__,
            "city_median_rate_per_1k": dict(city.medians), "attributes": list(ATTRIBUTES), "tracts": rows,
            "expected": expected, "regions": regions,
            "gaps": [{"tract_id": t, "expected": float(r.expected), "observed": float(r.observed),
                      "gap": None if pd.isna(r.gap) else float(r.gap)} for t, r in g.iterrows()],
            "rules": {"min_tracts": MIN_REGION_TRACTS, "min_group_tracts": MIN_GROUP_TRACTS, "min_voice": MIN_REGION_VOICE}}


# ----------------------------------------------------------------------------------------------- io
def load_real() -> City:
    tracts = pd.read_csv(D / "tracts.csv", dtype={"tract_id": str})
    comments = json.loads((PUB / "comments.json").read_text())["comments"] if (PUB / "comments.json").exists() else []
    comments = attach_location_basis(comments, D / "locations.csv")
    basis, part, bcounts = participation_basis(comments)
    r = json.loads((PUB / "requests_311_by_tract.json").read_text())
    by_cat = {t: {c: float(sum(m.values())) for c, m in cats.items()} for t, cats in r["by_tract"].items()}
    city = build_city(tracts, part, r["totals"], by_cat, int(r["months_covered"]))
    city.region_comments = comments
    city.problems_meta = {k: r.get(k) for k in ("category_labels", "taxonomy_source", "rows_not_problems")}
    city.location_basis = {"used": basis, **bcounts}
    city.all_located = build_city(tracts, comments, r["totals"], by_cat, int(r["months_covered"])) if basis != "all_located" else city
    # the per-tract 311 rate must match ingest_311's stored annualized rate
    for t, v in r.get("rate_per_1k_annualized", {}).items():
        if v is not None and t in city.rates["problems"].index:
            assert abs(city.rates["problems"][t] - v) < 0.01, (t, v, city.rates["problems"][t])
    return city


def jdump(p: Path, obj) -> None:
    p.write_text(json.dumps(obj, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


def meta(city: City) -> dict:
    return {"generated_at": datetime.now().astimezone().isoformat(timespec="seconds"), "aif360_version": aif360.__version__,
            "unit": "census tract (each tract one unit; population-weighted variant uses instance_weights = population)",
            "families": {"voice": ["letter", "email", "site"], "problems": ["311"]},
            "voice_location_basis": city.location_basis.get("used", "all_located"),
            "voice_location_basis_detail": {**city.location_basis, "rule": f"participation counts rows with location_basis in "
                f"{list(RESIDENCE_BASES)}; falls back to all located rows when fewer than {MIN_RESIDENCE_ROWS} have that basis; "
                "region/map counts always use all located rows"},
            "city_median_rate_per_1k": dict(city.medians), "median_over": f"all {len(city.tracts)} tracts, computed once",
            "outcome": OUTCOME, "favorable": "rate_per_1k > city_median_rate_per_1k",
            "attributes": {a: {**ATTRIBUTES[a], "threshold": city.thresholds[a], "privileged_value": 1, "unprivileged_value": 0,
                               "n_privileged": int((city.tracts[a] == 1).sum()), "n_unprivileged": int((city.tracts[a] == 0).sum())}
                           for a in ATTRIBUTES}, "attribute_default": DEFAULT_ATTR,
            "metrics": {"di": "P(fav|unprivileged) / P(fav|privileged)", "spd": "P(fav|unprivileged) - P(fav|privileged)",
                        "crosscheck": f"AIF360 vs pandas, |diff| <= {TOL}, asserted on every computation (weighted and unweighted)",
                        "aif360_weights": "BinaryLabelDatasetMetric base rates sum instance_weights, so instance_weights=population "
                                          "gives the population-weighted DI/SPD; verified equal to the pandas weighted formula"},
            "counting": {"voice_default": "duplicate_of rows dropped; each campaign_id counts once citywide (split evenly over its rows' tracts)",
                         "voice_raw": "every row counts 1 (exported as measure_raw_counts)",
                         "voice_rate": "per 1k residents over the corpus window (not annualized)",
                         "problems_rate": "per 1k residents, annualized via months_covered",
                         "unlocated_voice": "excluded from geography, reported in totals"},
            "correction": {"reweighing": "AIF360 Reweighing W(g,l)=P(g)P(l)/P(g,l) over tracts",
                           "population_weight": "population_share / comment_share per tract (voice only; null for tracts with no located comments)"},
            "gap": "expected = population_share x located voice total; gap = (expected - observed) / expected",
            "relevance": {"inside": RELEVANCE_INSIDE, "outside": RELEVANCE_OUTSIDE, "source": "public/data/affected.json"},
            "region_rule": {"not_enough_data_if": [f"tracts < {MIN_REGION_TRACTS}", f"privileged or unprivileged tracts < {MIN_GROUP_TRACTS}",
                                                   f"voice count < {MIN_REGION_VOICE}"], "outcome_median": "citywide (never recomputed)"},
            "problems_without_voice": {"problem_pct_min": fam.PROBLEM_PCT_MIN, "voice_pct_max": fam.VOICE_PCT_MAX},
            "wording": WORDING_RULES}


def run_real() -> int:
    city = load_real()
    OUT.mkdir(parents=True, exist_ok=True)
    affected = load_affected(sorted({c["item"] for c in city.comments}))
    taxonomy = load_taxonomy()
    voice = audit(city, "voice", affected=affected, taxonomy=taxonomy)
    voice["location_basis"] = city.location_basis
    variants = {}
    for name in ("residence", "all_located"):
        if name == "all_located":
            c2 = city.all_located
        else:
            res_rows = [c if c.get("location_basis") in RESIDENCE_BASES else {**c, "tract_id": None} for c in city.region_comments]
            c2 = city if city.location_basis.get("used") == "residence" else build_city(
                city.tracts.reset_index().rename(columns={"index": "tract_id"})[["tract_id", "population", "median_income", "pct_renter", "pct_nonwhite", "pct_lep"]],
                res_rows, city.problems_by_tract.to_dict(), city.problems_by_cat, city.months_covered)
        located = voice_counts(c2.comments, c2.tracts.index)["located"]
        if located == 0:
            variants[name] = {"status": "no_rows", "located": 0}
            continue
        u = c2.units("voice")
        variants[name] = {"status": "ok", "located": round(located, 9), "city_median_rate_per_1k": c2.medians["voice"],
                          "measure": measure_all(u), "underheard": underheard(participation_gaps(u, c2.voice_by_tract))}
    voice["location_basis_variants"] = variants
    prob = audit(city, "problems")
    jdump(OUT / "voice_city.json", voice)
    jdump(OUT / "311_city.json", prob)
    pwv = problems_without_voice_export(city)
    if voice["status"] != "ok":
        pwv = {**pwv, "status": "pending_locations", "rows": []}
    jdump(OUT / "problems_without_voice.json", pwv)
    jdump(OUT / "parity_fixtures.json", parity_fixtures())
    jdump(OUT / "meta.json", {**meta(city), "categories_source": taxonomy["categories_source"],
                               "categories": {"path": "data/categories.json", "authored_by": taxonomy["authored_by"],
                                              "version": taxonomy["version"], "keys": taxonomy["keys"]}})
    print_summary(city, voice, prob, pwv)
    return 0


def fmt(v):
    return "  n/a " if v is None else f"{v:6.3f}"


def print_summary(city: City, voice: dict, prob: dict, pwv: dict | None = None, synthetic_data: bool = False) -> None:
    print(f"AIF360 {aif360.__version__}; city medians per 1k: voice={city.medians['voice']:.4f} problems={city.medians['problems']:.2f}")
    for name, a in (("311 (synthetic)" if synthetic_data else "311 (real)", prob), (f"voice ({voice.get('label')})", voice)):
        print(f"\n{name}: status={a.get('status', 'ok')}")
        if "measure" not in a:
            continue
        print(f"  {'attribute':20s}   DI     SPD  | DI(pop) SPD(pop) | priv fav/n  unpriv fav/n")
        for at, m in a["measure"].items():
            u, w = m["unweighted"], m["population_weighted"]
            print(f"  {at:20s} {fmt(u['di'])} {fmt(u['spd'])} | {fmt(w['di'])} {fmt(w['spd'])}  | "
                  f"{u['privileged']['favorable']:3d}/{u['privileged']['n']:3d}     {u['unprivileged']['favorable']:3d}/{u['unprivileged']['n']:3d}")
    if voice.get("status") == "ok":
        print("\nunderheard (citywide):", [(r["tract_id"], round(r["gap"], 3), round(r["expected"], 2)) for r in voice["underheard"]])
        tr = voice["theme_rankings"]
        print("themes raw:", [(r["category"], r["rank"]) for r in tr["raw"]])
        print("themes aif360:", [(r["category"], r["rank"], r["rank_change"]) for r in tr["aif360_reweighted"]])
        print("themes pop:", [(r["category"], r["rank"], r["rank_change"]) for r in tr["population_reweighted"]])
    if pwv:
        print(f"\nproblems without voice: {len(pwv['rows'])} rows; zero-voice tracts={pwv['zero_voice_tracts']}")


def run_demo() -> int:
    tracts, comments, totals, by_cat = synthetic()
    city = build_city(tracts, comments, totals, by_cat, 12)
    voice, prob = audit(city, "voice"), audit(city, "problems")
    print("DEMO: synthetic tracts (seed 7, n=40); nothing written")
    print_summary(city, voice, prob, problems_without_voice_export(city), synthetic_data=True)
    ids = list(city.tracts.index)
    for sel in (ids[:20], ids[:4]):
        r = region_summary(sel, city)
        print(f"\nregion {len(sel)} tracts: not_enough_data={r['not_enough_data']} counts={r['counts']}")
        if not r["not_enough_data"]:
            print("  voice DI/SPD", fmt(r["voice"]["unweighted"]["di"]), fmt(r["voice"]["unweighted"]["spd"]),
                  "| 311 DI/SPD", fmt(r["requests_311"]["unweighted"]["di"]), fmt(r["requests_311"]["unweighted"]["spd"]))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    args, _ = ap.parse_known_args()
    sys.exit(run_demo() if args.demo else run_real())
