#!/usr/bin/env python3
"""Step a3: San José 311 Service Request Data (CKAN, CC0) -> per-tract counts. The real "problems" layer.

Source resources (dataset 5bd6605f-43fc-4ccc-b80b-3c15b5a02319):
  2026: d886727c-60f1-4be7-9a30-f6806375b1a3   2025: 761d15cc-0e89-46f4-a35b-0e586d746edf
Columns (inspected 2026-10-23, no published schema):
  Incident_ID, Status, Source, Category, Service Type, Latitude, Longitude, Date Created, Date Last Updated, Department
There is no address / zip / council-district column, so every row is located by point-in-polygon on
public/data/tracts.geojson and the coordinates are discarded. Default window: 2025-07-01 onward (--since).

Outputs:
  data/requests_311.csv                       normalized rows, no coordinates (gitignored: ~400k rows)
  public/data/requests_311_by_tract.json      counts per tract x category x month  (+ fixture copy)
  public/data/requests_311_sample.json        500 anonymized rows (seeded) for the inspector
  data/taxonomy_311.csv                       hand-filled Service Type (+Category) -> our category mapping
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "311"
TRACTS = ROOT / "public" / "data" / "tracts.geojson"
DISTRICTS = ROOT / "public" / "data" / "council_districts.geojson"
CSV_OUT = ROOT / "data" / "requests_311.csv"
BY_TRACT = ROOT / "public" / "data" / "requests_311_by_tract.json"
SAMPLE = ROOT / "public" / "data" / "requests_311_sample.json"
FIXTURE = ROOT / "public" / "data" / "fixtures" / "requests_311_by_tract.json"
UA = "CivicVoiceMap/0.1 (SJSU SpartHill hackathon; civic research)"
DATASET = "https://data.sanjoseca.gov/dataset/5bd6605f-43fc-4ccc-b80b-3c15b5a02319/resource"
RESOURCES = {2025: "761d15cc-0e89-46f4-a35b-0e586d746edf", 2026: "d886727c-60f1-4be7-9a30-f6806375b1a3"}

TAXONOMY = ROOT / "data" / "taxonomy_311.csv"
TRACTS_CSV = ROOT / "data" / "tracts.csv"


BOB_MAP = ROOT / "data" / "taxonomy_311_bob.json"
CATEGORIES = ROOT / "data" / "categories.json"


def apply_taxonomy(df: pd.DataFrame, log) -> pd.DataFrame:
    """311 request types -> the voice taxonomy's category keys, using IBM Bob's mapping of the 97 distinct
    (Service Type, Category) combinations (data/taxonomy_311_bob.json). 'none' = not a problem report (billing,
    accounts, service setup): kept in totals, excluded from the problems layer. The earlier hand mapping is kept as
    category_hand for comparison."""
    bob = pd.DataFrame(json.loads(BOB_MAP.read_text()))
    key = dict(zip(zip(bob["service_type"], bob["city_category"]), bob["category"]))
    st = df["category_raw"].fillna("(blank)")
    sub = df["subcategory_raw"].fillna("(blank)")
    df["category"] = [key.get(k) for k in zip(st, sub)]
    missing = df[df["category"].isna()]
    if len(missing):
        combos = missing.groupby(["category_raw", "subcategory_raw"], dropna=False).size()
        log(f"  {len(missing):,} rows in combos Bob has not mapped -> other: " + ", ".join(f"{a}/{b} {n}" for (a, b), n in combos.items()))
    df["category"] = df["category"].fillna("other")
    # hand mapping kept for comparison only
    hand = pd.read_csv(TAXONOMY, dtype=str).fillna("")
    spec = {(r.service_type, r.category_raw): r.category for r in hand.itertuples() if r.category_raw != "*"}
    gen = {r.service_type: r.category for r in hand.itertuples() if r.category_raw == "*"}
    df["category_hand"] = [spec.get((a, b)) or gen.get(a) or "other" for a, b in zip(df["category_raw"].fillna(""), df["subcategory_raw"].fillna(""))]
    return df


def download(year: int, log) -> Path:
    import httpx
    RAW.mkdir(parents=True, exist_ok=True)
    fn = RAW / f"311-service-requests-{year}.csv"
    if fn.exists() and fn.stat().st_size > 1_000_000:
        return fn
    url = f"{DATASET}/{RESOURCES[year]}/download/311-service-requests-{year}.csv"
    for attempt in range(4):
        try:
            with httpx.stream("GET", url, headers={"User-Agent": UA}, timeout=900, follow_redirects=True) as r:
                r.raise_for_status()
                with fn.open("wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)
            log(f"  downloaded {fn.name}: {fn.stat().st_size // 1_000_000} MB")
            return fn
        except Exception as e:
            log(f"  retry {attempt + 1} for {year}: {e!r}")
            time.sleep(2 ** attempt * 2)
    raise RuntimeError(f"could not download 311 {year}")


def load(since: str, log) -> pd.DataFrame:
    frames = []
    for year in sorted(RESOURCES):
        if str(year) < since[:4]:
            continue
        fn = download(year, log)
        df = pd.read_csv(fn, dtype=str)
        frames.append(df)
        log(f"  {year}: {len(df):,} rows")
    df = pd.concat(frames, ignore_index=True)
    df = df.rename(columns={"Incident_ID": "request_id", "Status": "status", "Source": "source", "Category": "subcategory_raw",
                            "Service Type": "category_raw", "Latitude": "lat", "Longitude": "lon",
                            "Date Created": "created_at", "Department": "department"})
    df["created_at"] = pd.to_datetime(df["created_at"], format="%m/%d/%Y %I:%M:%S %p", errors="coerce")
    df = df[df["created_at"] >= pd.Timestamp(since)].copy()
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    return apply_taxonomy(df, log)


def locate(df: pd.DataFrame, log) -> pd.DataFrame:
    import geopandas as gpd
    tracts = gpd.read_file(TRACTS)[["tract_id", "geometry"]]
    ok = df["lat"].between(36.9, 37.6) & df["lon"].between(-122.3, -121.4)
    log(f"  {(~ok).sum():,} rows with missing/out-of-area coordinates")
    pts = gpd.GeoDataFrame(df[ok], geometry=gpd.points_from_xy(df.loc[ok, "lon"], df.loc[ok, "lat"]), crs="EPSG:4326")
    joined = gpd.sjoin(pts, tracts, how="left", predicate="within")
    joined = joined[~joined.index.duplicated(keep="first")]
    df["tract_id"] = joined["tract_id"]
    df["council_district"] = pd.NA
    if DISTRICTS.exists():
        dist = gpd.read_file(DISTRICTS)[["district", "geometry"]]
        jd = gpd.sjoin(pts, dist, how="left", predicate="within")
        jd = jd[~jd.index.duplicated(keep="first")]
        df["council_district"] = jd["district"]
    df["location_precision"] = "none"
    df.loc[df["tract_id"].notna(), "location_precision"] = "point"
    log(f"  located in a San José tract: {df['tract_id'].notna().sum():,} of {len(df):,} ({df['tract_id'].notna().mean():.1%}); "
        f"the rest are outside the city tract set or lack coordinates")
    return df.drop(columns=["lat", "lon"])  # coordinates never leave data/raw/


def export(df: pd.DataFrame, since: str, log) -> None:
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    cols = ["request_id", "created_at", "category_raw", "subcategory_raw", "category", "category_hand", "status", "source", "department",
            "tract_id", "council_district", "location_precision"]
    df[cols].to_csv(CSV_OUT, index=False, date_format="%Y-%m-%dT%H:%M:%S")
    not_problem = df["category"] == "none"
    log(f"  {not_problem.sum():,} rows are billing/account/service requests (Bob: none) -> kept in totals, not in the problems layer")
    loc = df[df["tract_id"].notna() & ~not_problem].copy()
    loc["month"] = loc["created_at"].dt.strftime("%Y-%m")
    g = loc.groupby(["tract_id", "category", "month"]).size()
    by_tract: dict = {}
    for (t, c, m), n in g.items():
        by_tract.setdefault(t, {}).setdefault(c, {})[m] = int(n)
    totals = loc.groupby("tract_id").size().to_dict()
    pop = pd.read_csv(TRACTS_CSV, dtype={"tract_id": str}).set_index("tract_id")["population"].to_dict()
    months_n = max(1, loc["month"].nunique())
    rates = {t: round(n / pop[t] * 1000 * (12 / months_n), 2) for t, n in totals.items() if pop.get(t)}
    bob_map = json.loads(BOB_MAP.read_text())
    combos = pd.read_csv(ROOT / "data" / "taxonomy_311_combos.csv", dtype=str).fillna("")
    for m, n in zip(bob_map, combos["count"]):
        m["count"] = int(n)
    cats = json.loads(CATEGORIES.read_text())["categories"]
    payload = {"source": "San José Open Data: 311 Service Request Data (CC0), 2025 + 2026 yearly CSVs", "real": True,
               "since": since, "generated_at": date.today().isoformat(), "rows_total": int(len(df)), "rows_located": int(len(loc)),
               "categories": sorted(loc["category"].unique().tolist()),
               "taxonomy_source": "IBM Bob mapped the 97 distinct (Service Type, Category) combinations into the voice taxonomy",
               "taxonomy": bob_map, "category_labels": {c["key"]: c.get("label", c["key"]) for c in cats},
               "rows_not_problems": int(not_problem.sum()),
               "months": sorted(loc["month"].unique().tolist()), "months_covered": int(months_n),
               "totals": {k: int(v) for k, v in totals.items()},
               "rate_per_1k_annualized": rates, "population": {t: int(pop[t]) for t in totals if pop.get(t)},
               "by_tract": by_tract}
    BY_TRACT.write_text(json.dumps(payload, separators=(",", ":")))
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(BY_TRACT, FIXTURE)
    sample = loc.sample(n=min(500, len(loc)), random_state=7)[["request_id", "month", "category_raw", "subcategory_raw", "category", "status", "source", "tract_id", "council_district"]].copy()
    sample["subcategory_raw"] = sample["subcategory_raw"].where(sample["subcategory_raw"].notna(), None)
    sample["council_district"] = sample["council_district"].astype("object").where(sample["council_district"].notna(), None)
    SAMPLE.write_text(json.dumps({"real": True, "note": "seeded random 500 of the located rows (month only); the source has no address, free-text or requester fields, and coordinates are dropped",
                                  "rows": sample.to_dict(orient="records")}, indent=0, default=str))
    log(f"  wrote {CSV_OUT.relative_to(ROOT)} ({len(df):,} rows), {BY_TRACT.relative_to(ROOT)} ({len(by_tract)} tracts), sample of {len(sample)}")
    top = loc["category"].value_counts()
    log("  by category: " + ", ".join(f"{k} {v:,}" for k, v in top.items()))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default="2025-07-01", help="keep requests created on/after this date (default 2025-07-01)")
    ap.add_argument("--offline", action="store_true", help="copy the committed fixture to public/data, no download")
    args = ap.parse_args(argv)
    log = lambda s: print(s, file=sys.stderr, flush=True)
    if args.offline:
        shutil.copy(FIXTURE, BY_TRACT)
        log(f"[offline] copied 311 fixture")
        return 0
    if not TRACTS.exists():
        log(f"!! {TRACTS.relative_to(ROOT)} missing; run scripts/build_tracts.py first")
        return 1
    log(f"311 ingest since {args.since}")
    df = load(args.since, log)
    df = locate(df, log)
    export(df, args.since, log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
