#!/usr/bin/env python3
"""Milestone 3: census tracts, ACS demographics, council districts and a neighborhood lookup for San José.

Sources (all public, no key needed):
  City limits, council districts, neighborhoods  San José GIS ArcGIS REST (geo.sanjoseca.gov)
      PLN/PLN_AdministrativeBoundaries/MapServer/7   Incorporated (city limits)
      PLN/PLN_AdministrativeBoundaries/MapServer/1   City Council Districts (Current)
      OPN/OPN_OpenDataService/MapServer/549          Neighborhoods
    fallback for city limits: Census cartographic boundary place file (San Jose, PLACEFP 68000)
  Tracts   TIGER cartographic boundary file cb_<year>_06_tract_500k.zip (2024, then 2023)
  ACS 5-year (2024, then 2023, then 2022)
    The Census Data API now redirects key-less requests to missing_key.html, so by default we read the
    ACS table-based summary files on www2.census.gov (same estimates, pipe-delimited, one file per table)
    and keep only Santa Clara County rows. If CENSUS_API_KEY is set, the Data API is used instead.

Outputs:
  public/data/tracts.geojson             tract_id, name, aland   (clipped to city limits, simplified)
  public/data/council_districts.geojson  district (1-10)
  data/tracts.csv                        tract_id, population, median_income, pct_renter, pct_nonwhite, pct_lep
  data/blockgroups.csv                   block_group_id, tract_id, population, share_of_tract
  data/neighborhoods.csv                 name, aliases, lat, lon, tract_ids, source

Raw downloads are cached in data/raw/census/ (gitignored). --offline never touches the network: if every
output already exists it does nothing, otherwise it rebuilds from the cache.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import geopandas as gpd
import httpx
import numpy as np
import pandas as pd
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "census"
OUT_TRACTS_GEO = ROOT / "public" / "data" / "tracts.geojson"
OUT_DISTRICTS = ROOT / "public" / "data" / "council_districts.geojson"
OUT_TRACTS_CSV = ROOT / "data" / "tracts.csv"
OUT_BG = ROOT / "data" / "blockgroups.csv"
OUT_NBHD = ROOT / "data" / "neighborhoods.csv"
OUTPUTS = [OUT_TRACTS_GEO, OUT_DISTRICTS, OUT_TRACTS_CSV, OUT_BG, OUT_NBHD]

UA = "CivicVoiceMap/0.1 (SJSU SpartHill hackathon; civic research; 1 req/s)"
SJ_GIS = "https://geo.sanjoseca.gov/server/rest/services"
CITY_LAYER = f"{SJ_GIS}/PLN/PLN_AdministrativeBoundaries/MapServer/7"
DISTRICT_LAYER = f"{SJ_GIS}/PLN/PLN_AdministrativeBoundaries/MapServer/1"
NBHD_LAYER = f"{SJ_GIS}/OPN/OPN_OpenDataService/MapServer/549"
TIGER = "https://www2.census.gov/geo/tiger/GENZ{y}/shp/cb_{y}_06_{kind}_500k.zip"
ACS_SF = "https://www2.census.gov/programs-surveys/acs/summary_file/{y}/table-based-SF/data/5YRData/acsdt5y{y}-{t}.dat"
ACS_API = "https://api.census.gov/data/{y}/acs/acs5"

STATE, COUNTY = "06", "085"
TIGER_YEARS = [2024, 2023]
ACS_YEARS = [2024, 2023, 2022]
ACS_VARS = ["B01003_001E", "B25003_001E", "B25003_003E", "B19013_001E", "C16002_001E", "C16002_004E",
            "C16002_007E", "C16002_010E", "C16002_013E", "B03002_001E", "B03002_003E"]
EQUAL_AREA = "EPSG:3310"  # California Albers, metres
MIN_OVERLAP = 0.30
SIMPLIFY_DEG = 0.0003
NEAR_M = 1200


def log(msg: str) -> None:
    print(f"[build_tracts] {msg}", file=sys.stderr, flush=True)


# --------------------------------------------------------------------------------------------- network

class Client:
    """httpx wrapper: at most one request per second, retries with backoff on network errors and 5xx/429."""

    def __init__(self, offline: bool, delay: float = 1.0):
        self.offline = offline
        self.delay = delay
        self._last = 0.0
        self.c = httpx.Client(headers={"User-Agent": UA}, timeout=180, follow_redirects=True)

    def _wait(self):
        w = self.delay - (time.monotonic() - self._last)
        if w > 0:
            time.sleep(w)
        self._last = time.monotonic()

    def _retry(self, fn, url):
        if self.offline:
            raise RuntimeError(f"--offline and not cached: {url}")
        for attempt in range(5):
            self._wait()
            try:
                result = fn()
            except httpx.HTTPError as e:
                log(f"  {type(e).__name__} on {url} (attempt {attempt + 1}/5)")
                time.sleep(2 ** attempt)
                continue
            if result is None:  # retryable status
                time.sleep(2 ** attempt * 2)
                continue
            return result
        raise RuntimeError(f"gave up after 5 attempts: {url}")

    def get(self, url: str, **kw) -> httpx.Response:
        def once():
            r = self.c.get(url, **kw)
            return None if r.status_code in (429, 500, 502, 503, 504) else r
        return self._retry(once, url)

    def download(self, url: str, dest: Path) -> Path | None:
        """Download url to dest once (cached). Returns None on 404, or when offline and not cached."""
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        if self.offline:
            return None
        r = self.get(url)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(r.content)
        tmp.rename(dest)
        log(f"  downloaded {url} -> {dest.relative_to(ROOT)} ({dest.stat().st_size / 1e6:.1f} MB)")
        return dest

    def download_filtered(self, url: str, dest: Path, prefixes: tuple[str, ...]) -> Path | None:
        """Stream a pipe-delimited ACS summary file and keep the header plus lines starting with prefixes."""
        if dest.exists() and dest.stat().st_size > 0:
            return dest

        def once():
            kept = []
            with self.c.stream("GET", url) as r:
                if r.status_code in (429, 500, 502, 503, 504):
                    return None
                if r.status_code == 404:
                    return "404"
                r.raise_for_status()
                for i, line in enumerate(r.iter_lines()):
                    if i == 0 or line.startswith(prefixes):
                        kept.append(line)
            return kept

        kept = self._retry(once, url)
        if kept == "404":
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("\n".join(kept) + "\n")
        log(f"  streamed {url} -> {dest.relative_to(ROOT)} ({len(kept) - 1} county rows)")
        return dest

    def arcgis_geojson(self, layer_url: str, dest: Path, out_fields: str = "*") -> Path:
        """Query an ArcGIS REST layer as GeoJSON in WGS84, paging with resultOffset. Cached."""
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        features, offset = [], 0
        while True:
            r = self.get(f"{layer_url}/query", params={
                "where": "1=1", "outFields": out_fields, "outSR": 4326, "f": "geojson",
                "resultOffset": offset, "resultRecordCount": 1000, "orderByFields": "OBJECTID"})
            r.raise_for_status()
            page = r.json()
            if "error" in page:
                raise RuntimeError(f"ArcGIS error from {layer_url}: {page['error']}")
            features += page.get("features", [])
            if not page.get("properties", {}).get("exceededTransferLimit") and not page.get("exceededTransferLimit"):
                break
            offset += len(page.get("features", []))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
        log(f"  fetched {len(features)} features from {layer_url} -> {dest.relative_to(ROOT)}")
        return dest


# --------------------------------------------------------------------------------------------- geometry

def tiger_zip(cli: Client, kind: str) -> tuple[Path, int]:
    for y in TIGER_YEARS:
        path = cli.download(TIGER.format(y=y, kind=kind), RAW / f"cb_{y}_06_{kind}_500k.zip")
        if path:
            return path, y
        log(f"  cb_{y}_06_{kind}_500k.zip not available")
    raise RuntimeError(f"no TIGER {kind} file for {TIGER_YEARS}")


def city_boundary(cli: Client) -> tuple[gpd.GeoSeries, str]:
    try:
        path = cli.arcgis_geojson(CITY_LAYER, RAW / "sjgis_city_limits.geojson")
        city = gpd.read_file(path)
        if city.empty:
            raise RuntimeError("city limits layer returned no features")
        geom = city.to_crs(EQUAL_AREA).geometry.union_all()
        return gpd.GeoSeries([geom], crs=EQUAL_AREA), "San José GIS PLN_AdministrativeBoundaries/7 (Incorporated)"
    except Exception as e:  # noqa: BLE001 - any failure means fall back
        log(f"  city GIS unavailable ({e}); falling back to Census place boundary")
    path, y = tiger_zip(cli, "place")
    places = gpd.read_file(f"zip://{path}")
    sj = places[(places["PLACEFP"] == "68000")]
    geom = sj.to_crs(EQUAL_AREA).geometry.union_all()
    return gpd.GeoSeries([geom], crs=EQUAL_AREA), f"Census cb_{y}_06_place_500k (San Jose, PLACEFP 68000)"


def build_tracts(cli: Client) -> gpd.GeoDataFrame:
    city, city_src = city_boundary(cli)
    city_geom = city.iloc[0]
    log(f"city boundary: {city_src}, {city_geom.area / 1e6:.1f} km2")

    path, y = tiger_zip(cli, "tract")
    tracts = gpd.read_file(f"zip://{path}")
    tracts = tracts[tracts["COUNTYFP"] == COUNTY].to_crs(EQUAL_AREA)
    log(f"tracts: cb_{y}_06_tract_500k, {len(tracts)} in Santa Clara County")

    overlap = tracts.geometry.intersection(city_geom).area / tracts.geometry.area
    centroid_in = tracts.geometry.centroid.within(city_geom)
    keep = tracts[(overlap >= MIN_OVERLAP) | centroid_in].copy()
    log(f"  kept {len(keep)} tracts (overlap >= {MIN_OVERLAP:.0%}: {(overlap >= MIN_OVERLAP).sum()}, "
        f"centroid inside: {centroid_in.sum()})")

    keep["geometry"] = keep.geometry.intersection(city_geom)
    keep = keep.to_crs(4326)
    keep["geometry"] = keep.geometry.simplify(SIMPLIFY_DEG, preserve_topology=True)
    keep = keep[~keep.geometry.is_empty]
    out = gpd.GeoDataFrame({
        "tract_id": keep["GEOID"].astype(str).str.zfill(11),
        "name": keep["NAMELSAD"],
        "aland": keep["ALAND"].astype("int64"),
    }, geometry=keep.geometry.values, crs=4326).sort_values("tract_id").reset_index(drop=True)
    write_geojson(out, OUT_TRACTS_GEO)
    log(f"wrote {OUT_TRACTS_GEO.relative_to(ROOT)}: {len(out)} tracts")
    return out


def write_geojson(gdf: gpd.GeoDataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    gdf.to_file(path, driver="GeoJSON", COORDINATE_PRECISION=6, RFC7946="YES")


def build_districts(cli: Client) -> None:
    try:
        path = cli.arcgis_geojson(DISTRICT_LAYER, RAW / "sjgis_council_districts.geojson", "DISTRICT,DISTRICTINT")
    except Exception as e:  # noqa: BLE001
        log(f"council districts NOT written: {e}")
        return
    d = gpd.read_file(path)
    d = gpd.GeoDataFrame({"district": d["DISTRICTINT"].astype(int)}, geometry=d.geometry, crs=4326)
    d = d.dissolve(by="district").reset_index().sort_values("district")
    d["geometry"] = d.geometry.simplify(SIMPLIFY_DEG, preserve_topology=True)
    assert sorted(d["district"]) == list(range(1, 11)), sorted(d["district"])
    write_geojson(d[["district", "geometry"]], OUT_DISTRICTS)
    log(f"wrote {OUT_DISTRICTS.relative_to(ROOT)}: {len(d)} districts")


# --------------------------------------------------------------------------------------------- ACS

def sf_column(var: str) -> str:
    """API name B25003_003E -> summary-file name B25003_E003."""
    table, rest = var.split("_")
    return f"{table}_E{rest[:-1]}"


def acs_from_summary_files(cli: Client, year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (tract-level vars, block-group population) from the table-based summary files."""
    tract_prefix, bg_prefix = f"1400000US{STATE}{COUNTY}", f"1500000US{STATE}{COUNTY}"
    tables = sorted({v.split("_")[0].lower() for v in ACS_VARS})
    frames = {}
    for t in tables:
        dest = RAW / f"acs5_{year}_{t}_{STATE}{COUNTY}.psv"
        if cli.offline and not dest.exists():
            raise FileNotFoundError(dest)
        path = cli.download_filtered(ACS_SF.format(y=year, t=t), dest, (tract_prefix, bg_prefix))
        if path is None:
            raise FileNotFoundError(f"ACS {year} summary file for {t} not published")
        frames[t] = pd.read_csv(path, sep="|", dtype={"GEO_ID": str})

    tract = None
    for t, df in frames.items():
        cols = [v for v in ACS_VARS if v.split("_")[0].lower() == t]
        sub = df[df["GEO_ID"].str.startswith(tract_prefix)]
        sub = pd.DataFrame({"tract_id": sub["GEO_ID"].str[-11:].values,
                            **{v: pd.to_numeric(sub[sf_column(v)], errors="coerce").values for v in cols}})
        tract = sub if tract is None else tract.merge(sub, on="tract_id", how="outer")

    bg = frames["b01003"]
    bg = bg[bg["GEO_ID"].str.startswith(bg_prefix)]
    bg = pd.DataFrame({"block_group_id": bg["GEO_ID"].str[-12:].values,
                       "population": pd.to_numeric(bg["B01003_E001"], errors="coerce").values})
    return tract, bg


def acs_from_api(cli: Client, year: int, key: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    def call(params, cache):
        dest = RAW / cache
        if not dest.exists():
            if cli.offline:
                raise FileNotFoundError(dest)
            r = cli.get(ACS_API.format(y=year), params={**params, "key": key})
            if r.status_code != 200 or not r.headers.get("content-type", "").startswith("application/json"):
                raise FileNotFoundError(f"ACS API {year}: HTTP {r.status_code}")
            dest.write_text(r.text)
        rows = json.loads(dest.read_text())
        return pd.DataFrame(rows[1:], columns=rows[0])

    t = call({"get": ",".join(ACS_VARS), "for": "tract:*", "in": f"state:{STATE} county:{COUNTY}"},
             f"acs5_{year}_api_tracts.json")
    t["tract_id"] = t["state"] + t["county"] + t["tract"]
    t = t[["tract_id"] + ACS_VARS].copy()
    t[ACS_VARS] = t[ACS_VARS].apply(pd.to_numeric, errors="coerce")
    b = call({"get": "B01003_001E", "for": "block group:*", "in": f"state:{STATE} county:{COUNTY} tract:*"},
             f"acs5_{year}_api_blockgroups.json")
    b = pd.DataFrame({"block_group_id": b["state"] + b["county"] + b["tract"] + b["block group"],
                      "population": pd.to_numeric(b["B01003_001E"], errors="coerce")})
    return t, b


def load_acs(cli: Client) -> tuple[pd.DataFrame, pd.DataFrame, int, str]:
    key = os.environ.get("CENSUS_API_KEY", "").strip()
    for year in ACS_YEARS:
        try:
            if key:
                t, b = acs_from_api(cli, year, key)
                return t, b, year, "Census Data API"
            t, b = acs_from_summary_files(cli, year)
            return t, b, year, "ACS table-based summary files (www2.census.gov)"
        except (FileNotFoundError, httpx.HTTPStatusError) as e:
            log(f"  ACS {year} unavailable: {e}")
    raise RuntimeError(f"no ACS 5-year data for {ACS_YEARS}")


def ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    num, den = num.where(num >= 0), den.where(den > 0)  # negative values are ACS sentinels
    return (num / den).clip(0, 1).round(4)


def build_acs(cli: Client, tracts: gpd.GeoDataFrame) -> pd.DataFrame:
    t, bg, year, src = load_acs(cli)
    log(f"ACS 5-year {year} via {src}: {len(t)} county tracts, {len(bg)} block groups")
    t = t.set_index("tract_id")
    lep = t[["C16002_004E", "C16002_007E", "C16002_010E", "C16002_013E"]]
    lep_sum = lep.where(lep >= 0).sum(axis=1, min_count=4)
    out = pd.DataFrame({
        "population": t["B01003_001E"].where(t["B01003_001E"] >= 0),
        "median_income": t["B19013_001E"].where(t["B19013_001E"] >= 0),
        "pct_renter": ratio(t["B25003_003E"], t["B25003_001E"]),
        "pct_nonwhite": (1 - ratio(t["B03002_003E"], t["B03002_001E"])).round(4),
        "pct_lep": ratio(lep_sum, t["C16002_001E"]),
    })
    out = out.reindex(tracts["tract_id"]).rename_axis("tract_id").reset_index()
    out["population"] = out["population"].astype("Int64")
    out["median_income"] = out["median_income"].astype("Int64")
    out.to_csv(OUT_TRACTS_CSV, index=False)
    log(f"wrote {OUT_TRACTS_CSV.relative_to(ROOT)}: {len(out)} rows, population {int(out['population'].sum()):,}, "
        f"missing income {out['median_income'].isna().sum()}")

    bg = bg.copy()
    bg["population"] = bg["population"].where(bg["population"] >= 0).astype("Int64")
    bg["tract_id"] = bg["block_group_id"].str[:11]
    tract_pop = bg.groupby("tract_id")["population"].transform("sum")
    bg["share_of_tract"] = (bg["population"] / tract_pop.where(tract_pop > 0)).astype(float).round(4)
    bg = bg[["block_group_id", "tract_id", "population", "share_of_tract"]].sort_values("block_group_id")
    bg.to_csv(OUT_BG, index=False)
    log(f"wrote {OUT_BG.relative_to(ROOT)}: {len(bg)} block groups "
        f"({bg['tract_id'].isin(tracts['tract_id']).sum()} in San José tracts)")
    return out


# --------------------------------------------------------------------------------------------- neighborhoods

# (name, aliases, approx lat, approx lon, San José GIS neighborhood polygon names to snap to)
# Hand coordinates are approximate centres; when GIS polygons are listed the centroid of their union is used
# instead, and the hand value is only a sanity check (a warning is logged if they disagree by > 2.5 km).
NEIGHBORHOODS = [
    ("Downtown", "Downtown San Jose|Downtown San José|DTSJ|SoFA|SOFA District", 37.3355, -121.8880, ["Downtown and SOFA"]),
    ("Japantown", "Japan Town|Nihonmachi", 37.3490, -121.8950, ["Japantown and Hensley", "Japantown and Luna Park"]),
    ("Hensley", "Hensley Historic District", 37.3440, -121.8920, []),
    ("Jackson-Taylor", "Jackson Taylor", 37.3530, -121.8930, []),
    ("Northside", "North Side", 37.3560, -121.8800, ["Northside-Empire Gardens", "Northside-Grant", "Northside-Backesto"]),
    ("Luna Park", "", 37.3560, -121.8870, ["Luna Park"]),
    ("Vendome", "Vendome Ryland|Ryland", 37.3450, -121.8970, ["Vendome and Ryland"]),
    ("Naglee Park", "Naglee", 37.3360, -121.8730, ["Naglee"]),
    ("Roosevelt Park", "Roosevelt", 37.3460, -121.8710, ["Roosevelt"]),
    ("Olinder", "Olinder-McKinley|Brookwood Terrace", 37.3380, -121.8660, ["Olinder-McKinley", "Olinder-Brookwood Terrace"]),
    ("Five Wounds", "Five Wounds Brookwood Terrace|San Jose High", 37.3510, -121.8620, ["Five Wounds-San Jose High"]),
    ("Little Portugal", "Portuguese neighborhood", 37.3500, -121.8650, ["Little Portugal"]),
    ("Spartan Keyes", "Spartan-Keyes|Wool Creek", 37.3200, -121.8750, ["Spartan Keyes and Wool Creek"]),
    ("Washington-Guadalupe", "Washington Guadalupe|Guadalupe-Washington|Washington", 37.3180, -121.8870, ["Guadalupe Washington"]),
    ("Tamien", "Tamien Station", 37.3130, -121.8830, ["Tamien"]),
    ("Gardner", "Gardner neighborhood", 37.3200, -121.8960, ["Gardner"]),
    ("Delmas Park", "Delmas", 37.3270, -121.8970, ["Delmas Park"]),
    ("Sunol-Midtown", "Midtown|Sunol Midtown", 37.3260, -121.9030, []),
    ("Shasta Hanchett Park", "Shasta Hanchett|Shasta/Hanchett|Hanchett Park", 37.3300, -121.9130, ["Shasta/Hanchett Park"]),
    ("Rose Garden", "Rosegarden", 37.3330, -121.9250, ["Rose Garden"]),
    ("College Park", "Bellarmine", 37.3440, -121.9150, []),
    ("Burbank", "", 37.3230, -121.9310, ["Burbank"]),
    ("Buena Vista", "", 37.3190, -121.9200, []),
    ("Willow Glen", "WG|Lincoln Avenue", 37.3040, -121.8980, []),
    ("Winchester", "Winchester Boulevard|Winchester Blvd", 37.3100, -121.9500, []),
    ("West San José", "West San Jose|West SJ|Westgate", 37.3000, -121.9800, []),
    ("Calabazas", "", 37.3020, -122.0240, ["Calabazas"]),
    ("Lynbrook", "", 37.3010, -122.0050, []),
    ("Rancho Rinconada", "", 37.3110, -122.0110, []),
    ("Cambrian", "Cambrian Village", 37.2650, -121.9250, ["Cambrian"]),
    ("Cambrian Park", "", 37.2560, -121.9310, ["Cambrian Park"]),
    ("Erikson", "Branham Pearl", 37.2730, -121.8840, ["Branham/Pearl and Erikson"]),
    ("Almaden Valley", "Almaden|Almaden Valley San Jose", 37.2200, -121.8650, []),
    ("Blossom Valley", "Blossom Hill", 37.2540, -121.8350, ["Blossom Valley"]),
    ("Oak Grove", "", 37.2560, -121.8270, ["Oak Grove"]),
    ("Hoffman-Via Monte", "Hoffman Via Monte|Hoffman/Via Monte", 37.2450, -121.8820, ["Hoffman Via Monte"]),
    ("Santa Teresa", "", 37.2250, -121.7900, ["Santa Teresa"]),
    ("Edenvale", "", 37.2580, -121.8020, ["Edenvale"]),
    ("Coyote Valley", "Coyote|North Coyote Valley", 37.2000, -121.7400, []),
    ("Seven Trees", "7 Trees", 37.2920, -121.8380, ["Seven Trees and Lairon"]),
    ("Communications Hill", "Comm Hill", 37.2900, -121.8590, ["Communications Hill"]),
    ("Monterey Road corridor", "Monterey Road|Monterey Rd|Monterey Corridor", 37.2980, -121.8620, []),
    ("Santee", "Greater Santee", 37.3190, -121.8500, ["Greater Santee"]),
    ("Tully Road", "Tully Rd|Tully corridor", 37.3150, -121.8370, []),
    ("Story Road", "Story Rd|Story corridor", 37.3340, -121.8450, []),
    ("Little Saigon", "Saigon|Story and McLaughlin", 37.3300, -121.8460, ["Little Saigon and Spring Brook"]),
    ("King Road", "King Rd|King corridor", 37.3450, -121.8460, []),
    ("Mayfair", "", 37.3570, -121.8500, ["Mayfair"]),
    ("Alum Rock", "Alum Rock Avenue|Alum Rock Ave", 37.3680, -121.8330, []),
    ("East San José", "East San Jose|East Side|Eastside|East SJ", 37.3500, -121.8300, []),
    ("Capitol Expressway", "Capitol Expwy|Capitol corridor", 37.3250, -121.8150, []),
    ("Eastridge", "Eastridge Mall|Eastridge Center", 37.3263, -121.8122, []),
    ("Meadowfair", "Meadow Fair", 37.3190, -121.8180, ["Meadow Fair"]),
    ("Evergreen", "Evergreen Valley", 37.3100, -121.7800, []),
    ("Silver Creek", "Silver Creek Valley", 37.2970, -121.7750, []),
    ("Berryessa", "Berryessa San Jose", 37.3860, -121.8600, []),
    ("Berryessa Flea Market area", "Flea Market|Berryessa BART|Berryessa/North San Jose BART", 37.3690, -121.8740, ["Berryessa Flea Market-BART"]),
    ("Vinci Park", "", 37.3960, -121.8640, ["Vinci Park"]),
    ("North San José", "North San Jose|North First Street|Golden Triangle|NSJ", 37.4000, -121.9300, []),
    ("Alviso", "", 37.4260, -121.9740, ["Alviso"]),
]


def build_neighborhoods(cli: Client, tracts: gpd.GeoDataFrame) -> None:
    gis = None
    try:
        gis = gpd.read_file(cli.arcgis_geojson(NBHD_LAYER, RAW / "sjgis_neighborhoods.geojson", "NAME,SOURCE"))
        gis = gis[gis["NAME"].notna()].to_crs(EQUAL_AREA)
        gis = gis.dissolve(by="NAME").reset_index()
        log(f"neighborhoods: {len(gis)} named polygons from San José GIS")
    except Exception as e:  # noqa: BLE001
        log(f"  neighborhoods layer unavailable ({e}); using hand-entered centroids only")

    rows, used = [], set()
    for name, aliases, lat, lon, gis_names in NEIGHBORHOODS:
        pt = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(EQUAL_AREA).iloc[0]
        source = "hand"
        if gis is not None and gis_names:
            match = gis[gis["NAME"].isin(gis_names)]
            if len(match) != len(gis_names):
                log(f"  WARN {name}: GIS names not found {set(gis_names) - set(match['NAME'])}")
            if len(match):
                g = match.geometry.union_all()
                snapped = g.centroid if g.centroid.within(g) else g.representative_point()
                if snapped.distance(pt) > 2500:
                    log(f"  WARN {name}: GIS centroid is {snapped.distance(pt) / 1000:.1f} km from hand value")
                pt, source = snapped, "sjgis"
                used.update(match["NAME"])
        rows.append((name, aliases, pt, source))

    if gis is not None:  # every other named city neighborhood, as-is
        for _, r in gis[~gis["NAME"].isin(used)].iterrows():
            g = r.geometry
            pt = g.centroid if g.centroid.within(g) else g.representative_point()
            rows.append((r["NAME"], "", pt, "sjgis"))

    t = tracts.to_crs(EQUAL_AREA)
    t_cent = t.geometry.centroid
    out = []
    for name, aliases, pt, source in rows:
        containing = t[t.geometry.contains(pt)]["tract_id"].tolist()
        if not containing:  # in a county pocket / outside city: use the nearest San José tract
            containing = [t.loc[t.geometry.distance(pt).idxmin(), "tract_id"]]
        dist = t_cent.distance(pt)
        near = t.loc[dist[dist <= NEAR_M].sort_values().index, "tract_id"].tolist()
        ids = containing + [i for i in near if i not in containing]
        ll = gpd.GeoSeries([pt], crs=EQUAL_AREA).to_crs(4326).iloc[0]
        out.append({"name": name, "aliases": aliases, "lat": round(ll.y, 5), "lon": round(ll.x, 5),
                    "tract_ids": "|".join(ids), "source": source})
    df = pd.DataFrame(out)
    df.to_csv(OUT_NBHD, index=False)
    log(f"wrote {OUT_NBHD.relative_to(ROOT)}: {len(df)} neighborhoods "
        f"({len(NEIGHBORHOODS)} curated, {len(df) - len(NEIGHBORHOODS)} extra from GIS)")


# --------------------------------------------------------------------------------------------- checks

def verify() -> None:
    geo = gpd.read_file(OUT_TRACTS_GEO)
    csv = pd.read_csv(OUT_TRACTS_CSV, dtype={"tract_id": str})
    bg = pd.read_csv(OUT_BG, dtype={"block_group_id": str, "tract_id": str})
    nb = pd.read_csv(OUT_NBHD, keep_default_na=False)
    pop = int(csv["population"].sum())
    log(f"CHECK tracts: {len(geo)} (expect ~200-230)")
    log(f"CHECK population sum: {pop:,} (expect ~950k-1.0M)")
    missing = set(geo["tract_id"]) - set(csv["tract_id"])
    log(f"CHECK every geojson tract has a csv row: {not missing} {sorted(missing)[:5]}")
    coord_cols = [c for c in csv.columns if c.lower() in {"lat", "lon", "lng", "latitude", "longitude", "geometry", "x", "y"}]
    log(f"CHECK tracts.csv has no coordinate columns: {not coord_cols} {coord_cols}")
    ids_ok = geo["tract_id"].str.fullmatch(r"\d{11}").all()
    log(f"CHECK tract_id all 11 digits: {ids_ok}")
    for c in ["pct_renter", "pct_nonwhite", "pct_lep"]:
        log(f"CHECK {c} in [0,1]: {csv[c].dropna().between(0, 1).all()} (NaN {csv[c].isna().sum()})")
    log(f"CHECK neighborhoods without tracts: {(nb['tract_ids'] == '').sum()}")
    if OUT_DISTRICTS.exists():
        log(f"CHECK council districts: {sorted(gpd.read_file(OUT_DISTRICTS)['district'].tolist())}")
    with pd.option_context("display.width", 200, "display.max_columns", 10):
        print("\n== public/data/tracts.geojson (properties)\n", geo.drop(columns="geometry").head(3), file=sys.stderr)
        print("\n== data/tracts.csv\n", csv.head(3), file=sys.stderr)
        print("\n== data/blockgroups.csv\n", bg.head(3), file=sys.stderr)
        print("\n== data/neighborhoods.csv\n", nb.head(3), file=sys.stderr)
        if OUT_DISTRICTS.exists():
            print("\n== public/data/council_districts.geojson\n",
                  gpd.read_file(OUT_DISTRICTS).drop(columns="geometry").head(3), file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="no network; skip if outputs exist, else use the cache")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    if args.offline and all(p.exists() for p in OUTPUTS):
        log("--offline: all outputs exist, skipping build")
    else:
        cli = Client(offline=args.offline)
        tracts = build_tracts(cli)
        build_acs(cli, tracts)
        build_districts(cli)
        build_neighborhoods(cli, tracts)
    verify()
    return 0


if __name__ == "__main__":
    sys.exit(main())
