#!/usr/bin/env python3
"""Milestone 4: give every voice comment a census tract at the finest tier we can defend, and record that tier.

Precision ladder (finest first). A comment stops at the first tier that resolves:
  address       a street address (signature hint or an address block in the body/subject) via the US Census
                geocoder; a named intersection via San José GIS street centerlines; or an exact-name landmark from
                the hand gazetteer below. Point -> tract.
  neighborhood  a neighborhood name or alias (data/neighborhoods.csv) in the comment's neighborhood field, or in
                the body/subject next to a locative / residence cue -> the listed tract with the largest population.
  zip           a 95xxx ZIP (field or signature) -> ZCTA->tract crosswalk, tract with the largest estimated
                population in the overlap.
  district      no tract, but the writer states their council district ("I'm a District 3 resident").
  none          nothing usable. Still counted in totals, excluded from geography.

Privacy: raw addresses / intersections exist only in memory and in data/raw/. Outputs carry tract ids, tier,
source, district and a neighborhood/landmark name. The geocode cache is keyed by sha256(normalized query) and stores
only {tract_id, matched, source}.

Usage:
  python scripts/resolve_locations.py                 # letters + emails (when data/emails_raw.csv exists)
  python scripts/resolve_locations.py --input x.csv   # any CSV with comment_id, text (+ neighborhood, zip, ...)
  python scripts/resolve_locations.py --offline       # cache only, no network
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
DEFAULT_INPUTS = [DATA / "comments_raw.csv", DATA / "emails_raw.csv"]
HINT_FILES = [RAW / "legistar" / "location_hints.json", RAW / "emails" / "location_hints.json"]
NBHD_CSV = DATA / "neighborhoods.csv"
TRACTS_CSV = DATA / "tracts.csv"
TRACTS_GEO = ROOT / "public" / "data" / "tracts.geojson"
DISTRICTS_GEO = ROOT / "public" / "data" / "council_districts.geojson"
CACHE_PATH = DATA / "geocode_cache.json"
XWALK_RAW = RAW / "census" / "tab20_zcta520_tract20_95_06085.txt"
XWALK_URL = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_tract20_natl.txt"
XWALK_OUT = DATA / "zcta_tract_crosswalk.csv"
OUT_LOC = DATA / "locations.csv"
OUT_COV = ROOT / "public" / "data" / "coverage.json"

UA = "CivicVoiceMap/0.1 (SJSU hackathon; civic research; 1 req/s)"
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
STREETS_LAYER = "https://geo.sanjoseca.gov/server/rest/services/OPN/OPN_OpenDataService/MapServer/60"

TIERS = ["address", "neighborhood", "zip", "district", "none"]
BASES = ["residence", "issue", "both"]
OUT_COLS = ["comment_id", "tract_id", "location_precision", "location_source", "location_basis", "multi_tract",
            "council_district",
            "matched_name"]

# --------------------------------------------------------------------------------------------- gazetteer
# Coordinates come from the Census geocoder on each landmark's street address (Oct 2026), except SJSU (campus
# centroid; its 1 Washington Sq address does not geocode). Linear features (Coyote Creek Trail) have no point:
# a 30-mile trail says nothing about a tract, so it is listed with None and never resolves.
LANDMARKS: dict[str, tuple[Optional[float], Optional[float], list[str]]] = {
    "San José City Hall": (37.33816, -121.88622, ["City Hall", "San Jose City Hall"]),
    "San José State University": (37.33520, -121.88110, ["SJSU", "San Jose State University", "San Jose State"]),
    "Eastridge Mall": (37.32321, -121.81344, ["Eastridge Shopping Center", "Westfield Eastridge"]),
    "Lake Cunningham Park": (37.33904, -121.80378, ["Lake Cunningham"]),
    "Kelley Park": (37.32574, -121.86553, ["Kelly Park", "parque Kelley"]),
    "Happy Hollow": (37.32593, -121.86508, ["Happy Hollow Park", "Happy Hollow Zoo"]),
    "Emma Prusch Farm Park": (37.34226, -121.84551, ["Emma Prusch Park", "Prusch Park", "Prusch Farm"]),
    "Alum Rock Park": (37.39622, -121.80959, []),
    "Diridon Station": (37.32973, -121.90208, ["Diridon"]),
    "Santana Row": (37.32008, -121.94793, []),
    "Westfield Oakridge": (37.25047, -121.86648, ["Oakridge Mall"]),
    "Westfield Valley Fair": (37.32342, -121.94478, ["Valley Fair Mall"]),
    "SAP Center": (37.33214, -121.90052, ["Shark Tank"]),
    "Mexican Heritage Plaza": (37.35272, -121.85537, ["School of Arts and Culture"]),
    "Overfelt High School": (37.33008, -121.82923, ["Overfelt High"]),
    "Independence High School": (37.37085, -121.86306, ["Independence High"]),
    "Lincoln High School": (37.32924, -121.92386, ["Lincoln High"]),
    "Willow Glen High School": (37.29155, -121.89641, ["Willow Glen High"]),
    "Del Mar High School": (37.30325, -121.93031, ["Del Mar High"]),
    "Yerba Buena High School": (37.31964, -121.84713, ["Yerba Buena High"]),
    "Mt. Pleasant High School": (37.34474, -121.80874, ["Mt. Pleasant High", "Mount Pleasant High",
                                                         "Mount Pleasant High School"]),
    "Andrew Hill High School": (37.29341, -121.83311, ["Andrew Hill High"]),
    "Oak Grove High School": (37.25151, -121.81809, ["Oak Grove High"]),
    "Leland High School": (37.22117, -121.84942, ["Leland High"]),
    "Pioneer High School": (37.24834, -121.88244, ["Pioneer High"]),
    "San José High School": (37.35047, -121.87122, ["San Jose High", "San Jose High School", "San José High"]),
    "Silver Creek High School": (37.30416, -121.80826, ["Silver Creek High"]),
    "Evergreen Valley College": (37.29788, -121.76099, []),
    "San José City College": (37.31628, -121.92889, ["San Jose City College", "SJCC"]),
    "Guadalupe River Park": (37.34120, -121.90282, []),
    "St. James Park": (37.34095, -121.88871, ["St James Park", "Saint James Park"]),
    "Plaza de César Chávez": (37.33243, -121.88924, ["Plaza de Cesar Chavez", "Cesar Chavez Park"]),
    "Grand Century Mall": (37.33151, -121.85558, []),
    "Vietnam Town": (37.33227, -121.85422, []),
    "Berryessa BART": (37.37213, -121.87533, ["Berryessa/North San José station", "Berryessa station"]),
    "Tamien Station": (37.31159, -121.88217, []),
    "Alviso Marina": (37.42926, -121.97923, ["Alviso Marina County Park"]),
    "Martial Cottle Park": (37.26277, -121.83104, []),
    "San José Municipal Stadium": (37.32127, -121.86253, ["Municipal Stadium", "Excite Ballpark"]),
    "San José Mineta International Airport": (37.37150, -121.93040, ["SJC airport", "Mineta Airport",
                                                                     "San Jose airport", "San José airport"]),
    "300 Holger Way data center site": (37.41896, -121.94651, ["Holger Way"]),
    "Coyote Creek Trail": (None, None, []),
}

# Names that are common English words in /usr/share/dict/words are checked at runtime; this fallback keeps the
# behaviour stable where that file is missing.
GENERIC_FALLBACK = {"commercial", "union", "airport", "estates", "villages", "orchard", "cherry", "university",
                    "hammer", "glider", "checkers", "majestic", "cypress", "sundown", "mulberry", "southwest",
                    "reed", "alma", "monroe", "cahalan", "carden", "kirk", "muir", "parma", "hayes", "lido",
                    "poco", "dahl", "oster", "rogers", "williams", "redmond", "baldwin", "carlton", "coleman",
                    "brokaw", "branham", "metcalf", "starbird", "stokes", "guadalupe", "alameda", "fairground",
                    "civic center", "the plant", "the woods", "the willows", "the glens", "the villages", "park view"}

STREET_SUFFIX = (r"St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Way|Ct|Court|Ln|Lane|Pl|Place|Cir|Circle|"
                 r"Ter|Terrace|Expy|Expressway|Hwy|Highway|Pkwy|Parkway|Sq|Square")
MAJOR_TYPES = {"rd", "st", "ave", "blvd", "expy", "dr", "way", "pkwy", "hwy", "ln"}
TYPE_CANON = {"street": "st", "avenue": "ave", "road": "rd", "boulevard": "blvd", "drive": "dr", "lane": "ln",
              "court": "ct", "place": "pl", "circle": "cir", "terrace": "ter", "expressway": "expy",
              "highway": "hwy", "parkway": "pkwy", "square": "sq"}
# San José streets that people name without a suffix ("Story and King"); used only to pre-filter intersection
# candidates before the GIS lookup confirms them.
KNOWN_STREETS = {"story", "king", "tully", "alum rock", "monterey", "senter", "capitol", "santa clara", "first",
                 "second", "third", "fourth", "market", "almaden", "blossom hill", "hillsdale", "saratoga",
                 "stevens creek", "winchester", "bascom", "meridian", "camden", "branham", "curtner", "hamilton",
                 "julian", "taylor", "hedding", "berryessa", "mckee", "mabury", "lundy", "holger", "zanker",
                 "montague", "tasman", "brokaw", "oakland", "jackson", "coleman", "guadalupe", "william", "san carlos",
                 "san fernando", "san salvador", "keyes", "alma", "willow", "lincoln", "minnesota", "white",
                 "quimby", "aborn", "silver creek", "yerba buena", "mclaughlin", "jackson", "gold", "north first",
                 "fifth", "sixth", "seventh", "tenth", "eleventh", "24th", "33rd", "snell", "cottle", "santa teresa",
                 "great oaks", "hellyer", "lucretia", "ocala", "jose figueres", "white", "piedmont", "sierra",
                 "noble", "toyon", "flickinger", "capitol expressway", "lawrence", "de anza", "moorpark",
                 "naglee", "the alameda", "lincoln", "delmas", "minnesota"}

# ------------------------------------------------------------------------------------------- text utilities

def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm(s: str) -> str:
    s = strip_accents(str(s)).lower().replace("’", "'")
    s = re.sub(r"[-/]", " ", s)
    s = re.sub(r"[^a-z0-9' ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def clean_ocr(t: str) -> str:
    """OCR'd emails render 'I' as '|' or '1' ('| am', '1am', 'lam a resident')."""
    t = str(t or "").replace("’", "'").replace("\r", "")
    t = re.sub(r"(?<![\w|])\|(?=\s*(?:am|have|live|was|work|grew|'m|'ve)\b)", "I", t)
    t = re.sub(r"(?m)(^|[\s(])[1l]am\b", r"\1I am", t)
    t = re.sub(r"(?<![\w])\|'m\b", "I'm", t)
    return t


SIGNOFF = re.compile(r"^\s*(sincerely|thanks|thank you|best|regards|respectfully|warmly|cheers|cordially|"
                     r"with gratitude|in solidarity|yours|warm regards|kind regards|best regards|gracias|saludos)\b",
                     re.I)


def signature_block(text: str) -> str:
    lines = [l for l in text.split("\n") if l.strip()]
    idx = [i for i, l in enumerate(lines) if SIGNOFF.match(l)]
    if idx:
        return "\n".join(lines[idx[-1] + 1: idx[-1] + 13])
    return "\n".join(lines[-4:]) if len(lines) > 3 else ""


def strip_title_lines(text: str, title: str) -> str:
    """Drop leading lines that only repeat the agenda item title (common in forwarded comment emails)."""
    from rapidfuzz import fuzz
    if not title:
        return text
    tl = norm(title)
    lines = text.split("\n")
    out, checked = [], 0
    for i, l in enumerate(lines):
        nl = norm(l)
        if checked < 6 and nl:
            checked += 1
            if len(nl) >= 12 and (nl in tl or fuzz.partial_ratio(nl, tl) >= 85):
                continue
        out.append(l)
    return "\n".join(out)


def sentence_around(text: str, start: int, end: int) -> str:
    a = max(text.rfind(".", 0, start), text.rfind("\n\n", 0, start), text.rfind("!", 0, start),
            text.rfind("?", 0, start))
    bs = [p for p in (text.find(".", end), text.find("\n\n", end), text.find("!", end), text.find("?", end)) if p >= 0]
    return text[a + 1: (min(bs) if bs else len(text))]


# English, Spanish and Vietnamese first person (simulated emails include es/vi; norm() strips diacritics later)
FIRST_PERSON = re.compile(r"\b(I|I'm|I've|me|my|we|we're|our|us|vivo|vivimos|mi|mis|nuestro|nuestra|nosotros|"
                          r"tôi|chúng tôi)\b", re.I)
NEGATION = re.compile(r"\b(don't|do not|doesn't|never|not)\s+(?:\w+\s+){0,2}(live|reside|living)\b", re.I)
# locative / residence cue immediately before a place mention
CUE_BEFORE = re.compile(
    r"(?:\b(?:live|living|lived|reside|residing|resident|residents|homeowner|homeowners|neighbor|neighbors|grew up|"
    r"raised|home|house|block|street|corner|walk|walking|drive|work|here)\s+(?:\w+\s+){0,3}?)?"
    r"\b(?:in|at|near|around|on|off|across|along|throughout|part of|en|cerca de|cerca del|gần|ở khu|khu|tại)\s+"
    r"(?:the\s+|our\s+|my\s+|beautiful\s+|la zona de\s+)?"
    r"(?:\w+\s+)?$", re.I)
CUE_RESIDE_BEFORE = re.compile(
    r"\b(?:live|living|lived|reside|residing|resident|residents|homeowner|homeowners|neighbor|neighbors|grew up|"
    r"raised|here|rented|renting|rent|rents|renter|renters|tenant|tenants|been|own|owns|owner|units?|based|"
    r"households?)\b(?:\s+\w+){0,4}"
    r"\s+(?:in|at|near|by|on|of|off)\s+(?:the\s+|our\s+|my\s+)?$|"
    r"\b(?:vivo|vivimos|resido)\s+(?:en|cerca de|cerca del)\s+(?:la zona de\s+)?$|"
    r"\b(?:mi|nuestro)\s+(?:vecindario|barrio)\s+(?:en|cerca de|cerca del)\s+$|"
    r"\b(?:tôi|chúng tôi)\b[^.\n]{0,40}\b(?:gần|ở khu|ở)\s+$", re.I)
CUE_AFTER_PLACE = re.compile(r"^\s*(?:neighbou?rhood|area)\b", re.I)
CUE_AFTER_PERSON = re.compile(r"^\s*(?:resident|residents|homeowner|homeowners|neighbou?rs?|renter|renters|tenant|"
                              r"tenants|native|family|families|block)\b", re.I)
NEAR_BEFORE = re.compile(r"\b(?:near|by|around|next to|across from|across the street from|behind|along|outside|"
                         r"in front of|close to|walking distance (?:of|from|to)|blocks? from|cerca de|cerca del|"
                         r"junto a|junto al|gần)\s+(?:the\s+|el\s+|la\s+)?(?:parque\s+)?$", re.I)
WRITING = re.compile(r"\b(?:I'm|I am|I)\s+(?:writing|write)\b[^.]*", re.I)
MY_BEFORE = re.compile(r"\b(?:my|our)\s+(?:\w+\s+){0,1}$", re.I)
ORG_AFTER = re.compile(r"^\s*(?:union|unified|elementary|school district|community college|college|hall of fame|"
                       r"square|d\.?\s?c\b|high school|foundation|county|state\b|university|trustee)", re.I)
ORG_BEFORE = re.compile(r"\b(?:somos)\W*$", re.I)
SUFFIX_AFTER = re.compile(r"^\s*(?:" + STREET_SUFFIX + r")\b\.?", re.I)

NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
             "ten": 10}
DNUM = r"(10|[1-9]|one|two|three|four|five|six|seven|eight|nine|ten)\b"
DISTRICT_PATTERNS = [
    # "I'm a District 3 resident", "my husband and I have been residents of District 3", "I live in District 6"
    re.compile(r"\b(?:I|I'm|I am|we|we're|we are|my \w+ and I)\b[^.\n!?]{0,50}?\b(?:resident|residents|live|living|"
               r"reside|homeowner|property owner|constituent|neighbor)s?\b[^.\n!?]{0,15}?\b(?:in|of)\s+(?:the\s+)?"
               r"(?:San Jos[eé]\s+)?(?:Council\s+)?(?:District\s+|D-?)" + DNUM, re.I),
    re.compile(r"\b(?:I|I'm|I am|we|we're|we are|as a|my)\b[^.\n!?]{0,40}?\b(?:Council\s+)?(?:District\s+|D-?)" + DNUM +
               r"\s*(?:resident|homeowner|constituent|neighbor|voter)", re.I),
    # signature-style lines: "D3 Resident", "Resident District 2", "Resident of Council District 6"
    re.compile(r"(?m)^\s*(?:Council\s+)?(?:District\s+|D-?)" + DNUM + r"\s+Resident\b", re.I),
    re.compile(r"(?m)^\s*Resident(?:\s+of)?\s+(?:Council\s+)?District\s+" + DNUM, re.I),
    re.compile(r"(?m)^\s*(?:Council\s+)?District\s+" + DNUM + r"\s*,\s*[A-Z][a-z]+[^\n]{0,30}$"),
]
HOUSE_RE = re.compile(
    r"\b\d{1,5}\s+(?:[NSEW]\.?\s+)?(?:\d{1,2}(?:st|nd|rd|th)|[A-Z][A-Za-z'.-]*)(?:\s+[A-Z][A-Za-z'.-]*){0,3}\s+"
    r"(?:" + STREET_SUFFIX + r")\b\.?", re.I)
CITY_AFTER = re.compile(r"^[^\n]{0,40}?(?:\n[^\n]{0,40}?)?\b([A-Z][A-Za-z.]+(?:\s+[A-Z][A-Za-z.]+){0,2}),?\s*"
                        r"(?:CA|California)\b(?:\s*,?\s*(9\d{4}))?")
ADDR_CUE_BEFORE = re.compile(r"\b(?:live|living|reside|home|house|apartment|property)\s+(?:\w+\s+){0,2}"
                             r"(?:at|on)\s+$", re.I)
CITY_HALL = re.compile(r"^200\s+e(?:ast)?\.?\s+santa\s+clara", re.I)
ZIP_RE = re.compile(r"\b(9[0-6]\d{3})(?:-\d{4})?\b")


# ------------------------------------------------------------------------------------------- reference data

@dataclass
class Refs:
    tract_ids: set
    pop: dict
    tract_district: dict
    tract_geom: object = None      # GeoDataFrame
    nb_names: list = field(default_factory=list)   # (norm name, canonical, ntokens, curated)
    nb_tracts: dict = field(default_factory=dict)
    lm_names: list = field(default_factory=list)   # (norm alias, canonical)
    xwalk: dict = field(default_factory=dict)      # zcta -> (primary tract, multi)
    tract_pt: dict = field(default_factory=dict)   # tract -> (lon, lat) representative point
    nb_pt: dict = field(default_factory=dict)      # neighborhood -> (lon, lat) from neighborhoods.csv


def common_words() -> set:
    p = Path("/usr/share/dict/words")
    words = set(GENERIC_FALLBACK)
    if p.exists():
        words |= {w.strip() for w in p.read_text(errors="ignore").split() if w.strip() and w.strip().islower()}
    return words


def eligible_name(name: str, curated: bool, words: set) -> bool:
    """Generic SJ GIS names ("Commercial", "Union", "Estates") are not matched unless hand-curated."""
    n = norm(name)
    if curated:
        return len(n) >= 3
    if len(n.replace(" ", "")) < 5:
        return False
    if n in words or n in GENERIC_FALLBACK:
        return False
    toks = n.split()
    if toks and toks[0] == "the" and len(toks) == 2 and toks[1] in words:
        return False
    return True


def load_refs(with_geo: bool = True) -> Refs:
    tr = pd.read_csv(TRACTS_CSV, dtype={"tract_id": str})
    pop = dict(zip(tr.tract_id, tr.population.fillna(0).astype(float)))
    tract_district, gdf = {}, None
    if with_geo:
        import geopandas as gpd
        gdf = gpd.read_file(TRACTS_GEO)[["tract_id", "geometry"]]
        dist = gpd.read_file(DISTRICTS_GEO)[["district", "geometry"]]
        pts = gdf.copy()
        pts["geometry"] = gdf.geometry.representative_point()
        j = gpd.sjoin(pts, dist, how="left", predicate="within")
        tract_district = {t: (int(d) if pd.notna(d) else None) for t, d in zip(j.tract_id, j.district)}
    refs = Refs(tract_ids=set(pop), pop=pop, tract_district=tract_district, tract_geom=gdf)
    if gdf is not None:
        refs.tract_pt = {t: (p.x, p.y) for t, p in zip(gdf.tract_id, gdf.geometry.representative_point())}
    return add_names(refs, pd.read_csv(NBHD_CSV, dtype=str).fillna(""))


def add_names(refs: Refs, nb: pd.DataFrame, words: Optional[set] = None) -> Refs:
    """Neighborhood names/aliases (eligible ones only) and the landmark gazetteer -> refs."""
    words = common_words() if words is None else words
    for _, r in nb.iterrows():
        aliases = [a for a in r.aliases.split("|") if a]
        curated = r.source == "hand" or bool(aliases)
        tids = [t for t in r.tract_ids.split("|") if t in refs.tract_ids]
        if not tids:
            continue
        refs.nb_tracts[r["name"]] = tids
        try:
            refs.nb_pt[r["name"]] = (float(r["lon"]), float(r["lat"]))
        except (TypeError, ValueError):
            pass
        for n in [r["name"]] + aliases:
            if eligible_name(n, curated, words):
                nn = norm(n)
                refs.nb_names.append((nn, r["name"], len(nn.split()), curated))
    for canon, (lat, lon, aliases) in LANDMARKS.items():
        for a in [canon] + aliases:
            refs.lm_names.append((norm(a), canon))
    return refs


def load_crosswalk(refs: Refs, offline: bool) -> dict:
    if not XWALK_RAW.exists():
        if offline:
            print("  crosswalk: raw file missing and --offline; zip tier disabled", file=sys.stderr)
            return {}
        import httpx
        XWALK_RAW.parent.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", XWALK_URL, headers={"User-Agent": UA}, timeout=300) as r, \
                open(XWALK_RAW, "w") as f:
            r.raise_for_status()
            first = True
            for line in r.iter_lines():
                line = line.lstrip("﻿")
                cols = line.split("|")
                if first or (len(cols) > 10 and cols[1].startswith("95") and cols[9].startswith("06085")):
                    f.write(line + "\n")
                first = False
    x = pd.read_csv(XWALK_RAW, sep="|", dtype=str, encoding="utf-8-sig")
    x = x[x.GEOID_ZCTA5_20.notna() & x.GEOID_TRACT_20.isin(refs.tract_ids)].copy()
    x["arealand_part"] = x.AREALAND_PART.astype(float)
    x["tract_arealand"] = x.AREALAND_TRACT_20.astype(float)
    x["tract_population"] = x.GEOID_TRACT_20.map(refs.pop).astype(float)
    # residential share proxy: land overlap x tract population density = estimated people in the overlap
    x["est_pop"] = (x.arealand_part / x.tract_arealand.where(x.tract_arealand > 0)).fillna(0) * x.tract_population
    x["share"] = x.est_pop / x.groupby("GEOID_ZCTA5_20").est_pop.transform("sum")
    out = x.rename(columns={"GEOID_ZCTA5_20": "zcta", "GEOID_TRACT_20": "tract_id"})[
        ["zcta", "tract_id", "arealand_part", "tract_arealand", "tract_population", "est_pop", "share"]]
    out = out.sort_values(["zcta", "est_pop"], ascending=[True, False])
    out["est_pop"] = out.est_pop.round(1)
    out["share"] = out.share.round(4)
    out.to_csv(XWALK_OUT, index=False)
    res = {}
    for z, g in out.groupby("zcta"):
        if g.est_pop.sum() < 500:   # a sliver of one of our tracts: the ZIP is effectively outside San José
            continue
        res[z] = (g.iloc[0].tract_id, int((g.share >= 0.01).sum()) > 1)
    refs.xwalk = res
    return res


# ------------------------------------------------------------------------------------------- network lookups

class Cache:
    def __init__(self, path: Path):
        self.path = path
        self.d = json.loads(path.read_text()) if path.exists() else {}
        self.dirty = False

    @staticmethod
    def key(q: str) -> str:
        return hashlib.sha256(q.encode("utf-8")).hexdigest()

    def get(self, q: str):
        return self.d.get(self.key(q))

    def put(self, q: str, tract_id: Optional[str], matched: bool, source: str):
        self.d[self.key(q)] = {"tract_id": tract_id or "", "matched": bool(matched), "source": source}
        self.dirty = True

    def save(self):
        if self.dirty:
            self.path.write_text(json.dumps(dict(sorted(self.d.items())), indent=1) + "\n")


class Net:
    """Rate-limited (1 req/s) HTTP with retries/backoff. Returns None on failure so callers fall through."""

    def __init__(self, offline: bool):
        self.offline = offline
        self.last = 0.0
        self.client = None
        self.calls = 0
        self.failures = 0

    def get_json(self, url: str, params: dict) -> Optional[dict]:
        if self.offline:
            return None
        import httpx
        if self.client is None:
            self.client = httpx.Client(headers={"User-Agent": UA}, timeout=30)
        for attempt in range(4):
            wait = 1.0 - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            self.calls += 1
            try:
                r = self.client.get(url, params=params)
                if r.status_code == 200:
                    return r.json()
            except Exception:
                pass
            time.sleep(2 ** attempt)
        self.failures += 1
        return None


def point_tract(refs: Refs, lat: float, lon: float) -> Optional[str]:
    from shapely.geometry import Point
    if refs.tract_geom is None:
        return None
    p = Point(lon, lat)
    hit = refs.tract_geom[refs.tract_geom.covers(p)]   # covers: a point on a tract line still lands
    return hit.iloc[0].tract_id if len(hit) else None


def make_census_geocoder(refs: Refs, cache: Cache, net: Net) -> Callable[[str], Optional[str]]:
    def geocode(query: str) -> Optional[str]:
        q = "census|" + norm(query)
        c = cache.get(q)
        if c is not None:
            return c["tract_id"] or None
        js = net.get_json(CENSUS_URL, {"address": query, "benchmark": "Public_AR_Current",
                                       "vintage": "Current_Current", "format": "json"})
        if js is None:
            return None   # network failure: not cached, falls through
        m = (js.get("result") or {}).get("addressMatches") or []
        tid = None
        if m:
            geos = m[0].get("geographies", {}).get("Census Tracts", [])
            g = geos[0]["GEOID"] if geos else None
            if g in refs.tract_ids:
                tid = g
            else:
                co = m[0].get("coordinates", {})
                tid = point_tract(refs, co.get("y"), co.get("x")) if co else None
        cache.put(q, tid, bool(m), "census_onelineaddress")
        return tid
    return geocode


TYPE_SET = set(TYPE_CANON.values()) | {"st", "ave", "rd", "blvd", "dr", "ct", "ln", "pl", "way", "expy", "pkwy", "hwy",
                                       "cir", "ter", "sq", "loop"}
ORDMAP = {"first": "1st", "second": "2nd", "third": "3rd", "fourth": "4th", "fifth": "5th", "sixth": "6th",
          "seventh": "7th", "eighth": "8th", "ninth": "9th", "tenth": "10th", "eleventh": "11th"}
DIRS = {"n": "n", "s": "s", "e": "e", "w": "w", "north": "n", "south": "s", "east": "e", "west": "w"}
FREEWAYS = {"101", "280", "680", "880", "87", "85"}
STREET_NAMES_RAW = RAW / "sjgis" / "street_names.json"
STREET_GEOM_DIR = RAW / "sjgis" / "streets"


def _street_regex(name: str) -> tuple[str, Optional[str], str]:
    """'N First St' -> (base '1st', type 'st', direction 'n'); 'Story' -> ('story', None, '')."""
    toks = norm(name).replace(".", "").split()
    d = ""
    if len(toks) > 1 and toks[0] in DIRS:
        d, toks = DIRS[toks[0]], toks[1:]
    typ = None
    if len(toks) > 1 and TYPE_CANON.get(toks[-1], toks[-1]) in TYPE_SET:
        typ, toks = TYPE_CANON.get(toks[-1], toks[-1]), toks[:-1]
    if len(toks) > 1 and toks[-1] in DIRS:   # "N Bayshore W"
        toks = toks[:-1]
    return " ".join(ORDMAP.get(t, t) for t in toks), typ, d


class Streets:
    """San José street centerlines (SJ GIS OPN/OPN_OpenDataService/MapServer/60 'Streets', FULLNAME), public data
    cached under data/raw/sjgis/ so --offline can still anchor streets and compute intersections."""

    def __init__(self, net: "Net"):
        self.net = net
        self.bases: dict[str, set] = {}
        self._feats: dict[str, Optional[list]] = {}
        self._load_names()

    def _load_names(self):
        names = None
        if STREET_NAMES_RAW.exists():
            names = json.loads(STREET_NAMES_RAW.read_text())
        elif not self.net.offline:
            names, off = set(), 0
            while True:
                js = self.net.get_json(f"{STREETS_LAYER}/query", {
                    "where": "1=1", "outFields": "FULLNAME", "returnDistinctValues": "true",
                    "returnGeometry": "false", "orderByFields": "FULLNAME", "resultOffset": off,
                    "resultRecordCount": 2000, "f": "json"})
                if js is None:
                    names = None
                    break
                fs = js.get("features") or []
                names |= {f["attributes"]["FULLNAME"] for f in fs if f["attributes"].get("FULLNAME")}
                if len(fs) < 2000 and not js.get("exceededTransferLimit"):
                    break
                off += len(fs)
            if names:
                names = sorted(names)
                STREET_NAMES_RAW.parent.mkdir(parents=True, exist_ok=True)
                STREET_NAMES_RAW.write_text(json.dumps(names))
        for n in names or []:
            b, t, _ = _street_regex(n)
            if b:
                self.bases.setdefault(b, set()).add(t or "")
        if not self.bases:   # offline with no cache: fall back to the curated arterial list
            self.bases = {b: {""} for b in KNOWN_STREETS | FREEWAYS}

    def is_street(self, base: str) -> bool:
        return base in self.bases

    def _features(self, base: str) -> Optional[list]:
        if base in self._feats:
            return self._feats[base]
        path = STREET_GEOM_DIR / (re.sub(r"[^a-z0-9]+", "_", base) + ".geojson")
        feats = None
        if path.exists():
            feats = json.loads(path.read_text())["features"]
        elif not self.net.offline:
            b = base.upper().replace("'", "''")
            where = f"UPPER(FULLNAME) LIKE '{b} %' OR UPPER(FULLNAME) LIKE '% {b} %' OR UPPER(FULLNAME) = '{b}'"
            feats, off = [], 0
            while True:
                js = self.net.get_json(f"{STREETS_LAYER}/query", {"where": where, "outFields": "FULLNAME",
                                                                  "outSR": 4326, "f": "geojson",
                                                                  "resultOffset": off, "resultRecordCount": 2000})
                if js is None:
                    feats = None
                    break
                fs = js.get("features") or []
                feats += fs
                if len(fs) < 2000 or off > 20000:
                    break
                off += 2000
            if feats is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
        self._feats[base] = feats
        return feats

    def groups(self, name: str) -> dict:
        """{street type: merged geometry} for every SJ street with this base name (and type/direction if given)."""
        from shapely.geometry import shape
        from shapely.ops import unary_union
        base, typ, d = _street_regex(name)
        feats = self._features(base) if base else None
        out = defaultdict(list)
        for f in feats or []:
            if not f.get("geometry"):
                continue
            fb, ft, fd = _street_regex(f["properties"].get("FULLNAME", ""))
            if fb != base or (d and fd and fd != d):
                continue
            out[ft or ""].append(shape(f["geometry"]))
        if typ and typ in out:   # "Alma St." when only Alma Ave exists: keep every type rather than nothing
            out = {typ: out[typ]}
        return {t: unary_union(g) for t, g in out.items()}

    def geometry(self, name: str):
        """One street: the given type, else the longest major-type street of that name."""
        g = self.groups(name)
        if not g:
            return None
        major = {t: v for t, v in g.items() if t in MAJOR_TYPES or t == ""}
        pool = major or g
        return max(pool.values(), key=lambda v: v.length)

    def intersection(self, a: str, b: str):
        """Point where two named streets cross; None if they don't, or if their crossings are > ~1 km apart."""
        from shapely.geometry import MultiPoint
        from shapely.ops import nearest_points
        if _street_regex(a)[0] == _street_regex(b)[0]:
            return None
        ga, gb = self.groups(a), self.groups(b)
        for major_only in (True, False):
            pts = []
            for ta, geo_a in ga.items():
                for tb, geo_b in gb.items():
                    if major_only and not ((ta in MAJOR_TYPES or ta == "") and (tb in MAJOR_TYPES or tb == "")):
                        continue
                    inter = geo_a.intersection(geo_b)
                    if inter.is_empty:
                        if geo_a.distance(geo_b) < 0.00015:   # ~15 m: centerlines that just miss
                            pts.append(nearest_points(geo_a, geo_b)[0])
                        continue
                    pts += [g.centroid for g in getattr(inter, "geoms", [inter])]
            if pts:
                mp = MultiPoint(pts)
                minx, miny, maxx, maxy = mp.bounds
                return mp.centroid if max(maxx - minx, maxy - miny) < 0.01 else None
        return None


# ------------------------------------------------------------------------------------------- matching

@dataclass
class Mention:
    canon: str
    start: int
    end: int
    exact: bool


def find_mentions(text: str, names: list, threshold: int = 85) -> list[Mention]:
    """Token-aware matching: n-grams of the text vs names with the same token count; word boundaries only."""
    from rapidfuzz import fuzz
    toks = [(m.start(), m.end(), norm(m.group(0))) for m in re.finditer(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9'’.]*", text)]
    toks = [(s, e, t.rstrip(".")) for s, e, t in toks if t]
    by_n = defaultdict(list)
    exact = {}
    for nn, canon, *_ in names:
        k = len(nn.split())
        by_n[k].append((nn, canon))
        exact[nn] = canon
    out, used = [], set()
    for n in sorted(by_n, reverse=True):
        for i in range(len(toks) - n + 1):
            span = range(i, i + n)
            if any(j in used for j in span):
                continue
            # don't let a match cross a line break ("...Council\nDistrict")
            if "\n" in text[toks[i][0]:toks[i + n - 1][1]] and n > 1:
                continue
            cand = " ".join(toks[j][2] for j in span)
            if cand in exact:
                out.append(Mention(exact[cand], toks[i][0], toks[i + n - 1][1], True))
                used.update(span)
                continue
            if len(cand.replace(" ", "")) < 6:
                continue
            best, score = None, 0
            for nn, canon in by_n[n]:
                if nn[0] != cand[0] or abs(len(nn) - len(cand)) > 3:
                    continue
                s = fuzz.ratio(cand, nn)
                # every token must also look alike ("san jose i" is not "san jose high")
                if s >= threshold and min(fuzz.ratio(x, y) for x, y in zip(cand.split(), nn.split())) < 80:
                    continue
                if s > score:
                    best, score = canon, s
            if best and score >= threshold:
                out.append(Mention(best, toks[i][0], toks[i + n - 1][1], False))
                used.update(span)
    return sorted(out, key=lambda m: m.start)


SIG_FILLER = re.compile(r"\b(?:neighbou?rhood|area|resident|renter|homeowner|district\s+\w+|d-?\d+|san\s+jos[eé]|ca|"
                        r"california|95\d{3}|and|of|the|in|north|south|east|west)\b", re.I)


def signature_line(line: str, m: Mention) -> bool:
    """A short sign-off line that is essentially just a place ('Vendome neighborhood', 'District 3, Japantown')."""
    rest = SIG_FILLER.sub(" ", strip_accents(line.replace(line[line.find(line.strip()):], line.strip())))
    rest = re.sub(r"(?i)" + r"\s*".join(re.escape(w) for w in norm(m.canon).split()), " ", norm(rest))
    rest = re.sub(r"[^a-z]", "", norm(rest))
    return len(line.strip()) <= 60 and len(rest) <= 12


def mention_strength(text: str, m: Mention, sig_start: int) -> int:
    """3 residence cue, 2 signature line / 'X area', 1 locative preposition, 0 bare mention, -1 reject."""
    before = text[max(0, m.start - 70):m.start]
    after = text[m.end:m.end + 40]
    line_before = before.split("\n")[-1]
    if ORG_AFTER.match(after) or ORG_BEFORE.search(before) or \
            (SUFFIX_AFTER.match(after) and not MY_BEFORE.search(line_before)):   # "Almaden Rd" is a street
        return -1
    sent = sentence_around(text, m.start, m.end)
    if NEGATION.search(sent):
        return -1
    s0 = text.rfind(sent.strip()[:20], 0, m.end) if sent.strip() else -1
    prefix = text[s0:m.start] if 0 <= s0 <= m.start else line_before
    person_after = CUE_AFTER_PERSON.match(after) and (FIRST_PERSON.search(prefix) or len(prefix.strip(" -,(")) <= 3
                                                      or re.search(r"(\[name removed\]|\))\s*[,(—-]?\s*$", prefix)
                                                      or m.start >= sig_start)
    if CUE_RESIDE_BEFORE.search(line_before) or MY_BEFORE.search(line_before) or person_after or \
            (CUE_AFTER_PLACE.match(after) and FIRST_PERSON.search(sent)) or \
            (NEAR_BEFORE.search(line_before) and FIRST_PERSON.search(WRITING.sub(" ", prefix[-45:]))):
        # "our kids walk home in the dark near Story Rd" (first person close by; "I'm writing to ..." doesn't count)
        return 3
    if CUE_AFTER_PLACE.match(after):
        return 2
    if m.start >= sig_start:
        line = text[text.rfind("\n", 0, m.start) + 1: (text.find("\n", m.end) if text.find("\n", m.end) >= 0
                                                       else len(text))]
        if signature_line(line, m):
            return 2
    if CUE_BEFORE.search(line_before):
        return 1
    return 0


@dataclass
class Result:
    tract_id: str = ""
    precision: str = "none"
    source: str = ""
    multi: bool = False
    district: Optional[int] = None
    matched_name: str = ""
    basis: str = ""
    point: Optional[tuple] = None   # (lon, lat): in memory only, for item clusters; never written out


@dataclass
class Cand:
    rank: int            # 0 house address, 1 intersection/range, 2 landmark, 3 anchored street, 4 cluster-anchored
    source: str          # street, 5 neighborhood, 6 zip
    basis: str           # residence | issue | both
    pos: int
    tract_id: str = ""
    multi: bool = False
    matched_name: str = ""
    point: Optional[tuple] = None


@dataclass
class StreetMention:
    name: str
    base: str
    start: int
    end: int
    explicit: bool       # carried a suffix ("Alma Ave") or is a freeway number
    part: str = "body"


RANK_PRECISION = {0: "address", 1: "address", 2: "address", 3: "address", 4: "address", 5: "neighborhood", 6: "zip"}
BASIS_ORDER = {"residence": 0, "both": 0, "issue": 1}
SUFFIX_WORDS = {"st", "street", "ave", "avenue", "blvd", "boulevard", "rd", "road", "dr", "drive", "way", "ct",
                "court", "ln", "lane", "pl", "place", "cir", "circle", "ter", "terrace", "expy", "expressway", "hwy",
                "highway", "pkwy", "parkway"}
ABBREV = {"st", "ave", "rd", "blvd", "dr", "ln", "ct", "expy", "pkwy", "hwy"}
# "Cedar Court Apartments", "Terra Verde Plaza": a named building/project, not a street (fictional or not, it is
# never geocoded by name; the real street or area it is "near"/"off" anchors it)
FAKE_AFTER = re.compile(r"^\s*(?:apartments?|apts?\b|plaza|center|centre|mall|homes|village|complex|towers?|condos?|"
                        r"lofts|school|elementary|library|shopping|business park|data center|project)\b", re.I)
STREET_PREP = re.compile(r"(?:\b(?:on|along|off|onto|down|up|cross|crossing|near|by|at|across|en|cerca de|cerca del|"
                         r"gần|khu|ở|đường)|\bal)\s+(?:the\s+|la\s+|el\s+)?$", re.I)
STRONG_STREET_PREP = re.compile(r"\b(?:on|along|off|onto|down|up|cross|crossing|đường)\s+(?:the\s+)?$", re.I)
FREEWAY_RE = re.compile(r"\b(?:(?:US|U\.S\.|Hwy|Highway|Interstate|I|SR|Route|CA)[- ]?(101|280|680|880|87|85)\b|"
                        r"the (101|280|680|880|87|85)\b|(?:by|near|along|off|on|next to)\s+(101|280|680|880|87|85)\b|(101|280|680|880|87|85)\s+(?:freeway|fwy|highway|overpass|"
                        r"underpass|on-?ramp|off-?ramp|exit|interchange))", re.I)
PAIR_BETWEEN = re.compile(r"^\s*(?:and|&|/|@|at|y|và|with|x)\s*$", re.I)
NEAR_BETWEEN = re.compile(r"^\s*,?\s*(?:just\s+)?(?:near|by|close to|cerca de|cerca del|gần|off)\s+(?:the\s+)?$", re.I)
RANGE_FROM = re.compile(r"^\s*,?\s*(?:between|from|entre|giữa)\s+$", re.I)
RANGE_AND = re.compile(r"^\s*(?:and|to|y|&|và)\s+$", re.I)
PROX_FIRST = re.compile(r"\b(?:I|I'm|I've|we|we're|my|our|me|vivo|mi|mis|tôi|chúng tôi)\b[^.\n!?]{0,40}\b(?:live|living|"
                        r"walk|walking|cross|crossing|drive|driving|commute|bike|biking|home|homes|block|street|"
                        r"neighbou?rs?|shop|kids|family|rent|rents|apartment|house|vecindario|barrio|nhà)\b"
                        r"[^.\n!?]{0,30}$", re.I)
AFFIL_BEFORE = re.compile(r"\b(?:graduate[ds]?|alumn\w*|student|professor|faculty|director|staff|employee|employed|"
                          r"hired|program|position|work(?:s|ed|ing)?|trustee|board|chair\w*|serves?|served|"
                          r"volunteer\w*|president|met|known|attended|attends|studied|taught|teach(?:es|ing)?)\b"
                          r"[^.\n]{0,40}\b(?:at|of|from|with|for|in)\s+(?:the\s+)?$", re.I)
ANCHOR_MAX_DEG = 0.03    # ~3 km: a co-mentioned place further than this from the street is not its anchor
CLUSTER_MAX_DEG = 0.05   # ~5 km
M300_DEG = 0.0027        # 300 m in degrees latitude


def residence_cue(text: str, start: int, end: int, sig_start: int, canon: str = "") -> bool:
    m = Mention(canon or text[start:end], start, end, True)
    if mention_strength(text, m, sig_start) >= 3:
        return True
    before = WRITING.sub(" ", text[max(0, start - 80):start].split("\n")[-1])
    return bool(PROX_FIRST.search(before))


_WORDS: Optional[set] = None


def _common(w: str) -> bool:
    global _WORDS
    if _WORDS is None:
        _WORDS = common_words()
    return w in _WORDS


def find_streets(text: str, streets, nb_norms: set) -> list[StreetMention]:
    """Street mentions: '<name> <suffix>' validated against SJ street names, bare arterial names ('Story', '5th'),
    and freeway numbers. Bare names are kept with explicit=False; callers decide whether they stand alone."""
    toks = [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"[A-Za-zÀ-ỹ0-9]+(?:['’][A-Za-z]+)?\.?", text)]
    out, used = [], set()
    for i, (s, e, raw) in enumerate(toks):
        w = norm(raw)
        if w not in SUFFIX_WORDS or i == 0 or FAKE_AFTER.match(text[e:e + 30]):
            continue
        for k in (3, 2, 1):
            j = i - k
            if j < 0 or any(x in used for x in range(j, i)) or "\n" in text[toks[j][0]:e]:
                continue
            name = text[toks[j][0]:e]
            b, _, _ = _street_regex(name)
            if not b or not streets.is_street(b) or b in {"the", "my", "our", "this", "that", "a"}:
                continue
            cap = toks[j][2][:1].isupper() or toks[j][2][:1].isdigit()
            if not cap and not (w in ABBREV or b in KNOWN_STREETS):
                continue
            if j > 0 and norm(toks[j - 1][2]) in DIRS and toks[j - 1][2][:1].isupper() and \
                    "\n" not in text[toks[j - 1][0]:toks[j][0]]:
                j -= 1
                name = text[toks[j][0]:e]
            out.append(StreetMention(name, b, toks[j][0], e, True))
            used.update(range(j, i + 1))
            break
    for m in FREEWAY_RE.finditer(text):
        num = next(g for g in m.groups() if g)
        if streets.is_street(num) and not any(x.start <= m.start() < x.end for x in out):
            out.append(StreetMention(num, num, m.start(), m.end(), True))
    for i, (s, e, raw) in enumerate(toks):
        # lowercase only right after on/along/off ("off tully"), never a dictionary word ("on the market")
        lower_ok = (re.search(r"\b(?:on|along|off|onto)\s+$", text[max(0, s - 12):s], re.I) and len(raw) >= 4
                    and not _common(norm(raw)))
        if i in used or not (raw[:1].isupper() or raw[:1].isdigit() or lower_ok):
            continue
        for k in (2, 1):
            if i + k > len(toks) or any(x in used for x in range(i, i + k)):
                continue
            span_end = toks[i + k - 1][1]
            b = _street_regex(text[s:span_end])[0]
            ordinal = re.fullmatch(r"\d{1,2}(?:st|nd|rd|th)", b or "")
            if not (b in KNOWN_STREETS or ordinal) or not streets.is_street(b):
                continue
            nxt = toks[i + k][2] if i + k < len(toks) else ""
            gap = text[span_end:toks[i + k][0]] if i + k < len(toks) else ""
            if nxt[:1].isupper() and not gap.strip() and "\n" not in gap and not text[span_end - 1] == ".":
                continue   # part of a longer proper noun ("Willow Glen", "Santa Clara County")
            out.append(StreetMention(text[s:span_end].rstrip("."), b, s, span_end, False))
            used.update(range(i, i + k))
            break
    return sorted(out, key=lambda m: m.start)


class Resolver:
    def __init__(self, refs: Refs, geocode: Callable[[str], Optional[str]], streets, hints: dict):
        self.refs, self.geocode, self.streets, self.hints = refs, geocode, streets, hints
        self.stats = Counter()
        self.nb_norms = {n for n, *_ in refs.nb_names} | {n for n, _ in refs.lm_names}

    # -- helpers
    def primary_tract(self, nb: str) -> tuple[str, bool]:
        tids = self.refs.nb_tracts[nb]
        best = max(tids, key=lambda t: self.refs.pop.get(t, 0))
        return best, len(tids) > 1

    def title_places(self, title: str) -> set:
        t = title or ""
        names = {m.canon for m in find_mentions(t, self.refs.nb_names)}
        names |= {m.canon for m in find_mentions(t, self.refs.lm_names, 90)}
        names |= {"street:" + m.base for m in find_streets(t, self.streets, self.nb_norms)}
        return names

    def stated_district(self, parts: list[tuple[str, str]]) -> tuple[Optional[int], str]:
        for src, t in parts:
            for p in DISTRICT_PATTERNS:
                m = p.search(t)
                if m:
                    g = m.group(1).lower()
                    return (NUM_WORDS.get(g) or int(g)), src
        return None, ""

    def street_multi(self, geom, pt) -> bool:
        """True when the street crosses tract lines within 300 m of the anchored point."""
        import math
        from shapely.affinity import scale
        if self.refs.tract_geom is None or geom is None:
            return False
        buf = scale(pt.buffer(M300_DEG), xfact=1 / math.cos(math.radians(pt.y)), yfact=1.0)
        seg = geom.intersection(buf)
        if seg.is_empty:
            return False
        return int(self.refs.tract_geom.intersects(seg).sum()) > 1

    def point_cand(self, rank, source, basis, pos, pt, multi=False, name="") -> Optional[Cand]:
        tid = point_tract(self.refs, pt.y, pt.x)
        if not tid:
            self.stats["point_outside_tracts"] += 1
            return None
        return Cand(rank, source, basis, pos, tid, multi, name, (pt.x, pt.y))

    @staticmethod
    def basis(cue: bool, key: str, title_pl: set, subject: str, mentioned_in_subject: bool) -> str:
        if not cue:
            return "issue"
        return "both" if (key in title_pl or mentioned_in_subject) else "residence"

    # -- candidates
    def address_cands(self, cid, parts, row) -> tuple[list[Cand], list[tuple[int, int, str]]]:
        """House-number addresses. Returns candidates and the consumed spans (so their street isn't reused)."""
        body = dict(parts).get("body", "")
        h = self.hints.get(cid) or {}
        raw = []
        if h.get("address"):
            raw.append(("signature", h["address"], h.get("zip", ""), "residence", -1))
        spans = []
        for src, t in parts:
            for m in HOUSE_RE.finditer(t):
                spans.append((m.start(), m.end(), src))
                after, before = t[m.end():m.end() + 90], t[max(0, m.start() - 40):m.start()]
                blk = CITY_AFTER.match(after)
                # an address block (letterhead/signature) or "I live at ..." is where the writer is;
                # an address inside a sentence is what the comment is about (project site, problem spot)
                basis = "residence" if (blk or ADDR_CUE_BEFORE.search(before)) else "issue"
                raw.append((src, m.group(0), (blk.group(2) or "") if blk else "", basis, m.start()))
        out, seen = [], set()
        for src, addr, z, basis, pos in raw:
            a = re.sub(r"\s+", " ", addr).strip().rstrip(".")
            if norm(a) in seen:
                continue
            seen.add(norm(a))
            if CITY_HALL.match(a):
                self.stats["address_skipped_cityhall"] += 1
                continue
            city, zip_ = "San Jose", z
            toks = a.split()
            i = body.find(toks[0] + " " + toks[1]) if len(toks) > 1 else -1
            if i >= 0:
                blk = CITY_AFTER.match(body[i + len(a): i + len(a) + 90])
                if blk:
                    city, zip_ = blk.group(1), blk.group(2) or zip_
            if not re.search(r"(?:^| )san ?jose$", norm(city)):
                self.stats["address_outside_sj"] += 1
                continue
            tid = self.geocode(f"{a}, San Jose, CA" + (f" {zip_}" if zip_ else ""))
            if tid:
                if h.get("address") and norm(a) == norm(h["address"]):
                    src, basis = "signature", "residence"
                out.append(Cand(0, src, basis, pos, tid, False, "", self.refs.tract_pt.get(tid)))
        return out, spans

    def place_mentions(self, parts, row) -> tuple[list, list]:
        """Accepted neighborhood and landmark mentions: (part, Mention, strength, residence?, sig_start)."""
        nbs, lms = [], []
        for src, t in parts:
            sig = signature_block(t) if src == "body" else ""
            sig_start = t.rfind(sig) if sig else len(t)
            for m in find_mentions(t, self.refs.nb_names):
                st = mention_strength(t, m, sig_start)
                if st < 0:
                    continue
                res = st >= 3 or (st == 2 and m.start >= sig_start)
                nbs.append((src, m, st, res, sig_start))
            for m in find_mentions(t, self.refs.lm_names, 92):
                st = mention_strength(t, m, sig_start)
                before = t[max(0, m.start - 70):m.start].split("\n")[-1]
                line = t[t.rfind("\n", 0, m.start) + 1:(t.find("\n", m.end) if t.find("\n", m.end) >= 0 else len(t))]
                in_sig = m.start >= sig_start and len(line.strip()) <= 70
                institution = bool(re.search(r"(?i)university|college|high school|\bsjsu\b|\bsjcc\b|san jos[eé] state",
                                             m.canon + " " + t[m.start:m.end]))
                if st < 0 or (AFFIL_BEFORE.search(before) and st < 3):
                    continue   # "graduate of SJSU", "worked with him at San José State"
                if institution and not (st >= 3 or NEAR_BEFORE.search(before) or in_sig):
                    continue   # an employer or alma mater is not where the comment is
                if st < 1 and src != "subject" and not in_sig:
                    continue   # "transit mega-projects (such as Diridon Station)" is an example, not a place
                if in_sig and st < 3:
                    st = 2   # signature/letterhead affiliation: the organisation's base
                res = st >= 3 or (st == 2 and m.start >= sig_start)
                lms.append((src, m, st, res, sig_start))
        return nbs, lms

    def street_cands(self, parts, consumed, anchors, title_pl, subject):
        """Intersections, ranges, 'X near Y', and single streets anchored to a cross street or a co-mentioned
        place. Returns (candidates, pending single streets for the item-cluster pass)."""
        from shapely.ops import nearest_points
        from shapely.geometry import Point
        cands, pending = [], []
        for src, t in parts:
            sig = signature_block(t) if src == "body" else ""
            sig_start = t.rfind(sig) if sig else len(t)
            ms = [m for m in find_streets(t, self.streets, self.nb_norms)
                  if not any(a <= m.start < b and s == src for a, b, s in consumed)]
            for m in ms:
                m.part = src
            used = set()

            def cue_basis(a, b, key):
                if NEGATION.search(sentence_around(t, a, b)):
                    return None
                return self.basis(residence_cue(t, a, b, sig_start), key, title_pl, subject,
                                  src == "subject" or key.replace("street:", "") in norm(subject))

            # ranges: "King Road between Story and Tully" -> midpoint of the two crossings
            for i in range(len(ms) - 2):
                m1, m2, m3 = ms[i], ms[i + 1], ms[i + 2]
                if RANGE_FROM.match(t[m1.end:m2.start]) and RANGE_AND.match(t[m2.end:m3.start]):
                    p1, p2 = self.streets.intersection(m1.name, m2.name), self.streets.intersection(m1.name, m3.name)
                    pts = [p for p in (p1, p2) if p is not None]
                    b = cue_basis(m1.start, m3.end, "street:" + m1.base)
                    if pts and b:
                        pt = Point(sum(p.x for p in pts) / len(pts), sum(p.y for p in pts) / len(pts))
                        c = self.point_cand(1, "intersection", b, m1.start, pt,
                                            multi=self.street_multi(self.streets.geometry(m1.name), pt))
                        if c:
                            cands.append(c)
                            used |= {i, i + 1, i + 2}
            # pairs: "Story and King", "King & Story", "Story/King", "5th and William", "X near Y"
            for i in range(len(ms) - 1):
                if i in used or i + 1 in used:
                    continue
                m1, m2 = ms[i], ms[i + 1]
                btw = t[m1.end:m2.start]
                is_pair, is_near = PAIR_BETWEEN.match(btw), NEAR_BETWEEN.match(btw)
                if not (is_pair or is_near):
                    continue
                b = cue_basis(m1.start, m2.end, "street:" + m1.base)
                if not b:
                    continue
                pt = self.streets.intersection(m1.name, m2.name)
                if pt is not None:
                    c = self.point_cand(1, "intersection", b, m1.start, pt)
                    if c:
                        cands.append(c)
                        used |= {i, i + 1}
                elif is_near and m1.explicit:
                    g1, g2 = self.streets.geometry(m1.name), self.streets.geometry(m2.name)
                    if g1 is not None and g2 is not None and g1.distance(g2) < ANCHOR_MAX_DEG:
                        pt = nearest_points(g1, g2)[0]
                        c = self.point_cand(3, "street_anchor", b, m1.start, pt, self.street_multi(g1, pt))
                        if c:
                            cands.append(c)
                            used |= {i, i + 1}
            # single streets
            for i, m in enumerate(ms):
                if i in used:
                    continue
                before = t[max(0, m.start - 40):m.start]
                if not m.explicit:
                    if not STREET_PREP.search(before):
                        continue
                    if m.base in self.nb_norms and not STRONG_STREET_PREP.search(before):
                        continue   # "near Berryessa" is the neighborhood; "on Berryessa" is the road
                b = cue_basis(m.start, m.end, "street:" + m.base)
                if not b:
                    continue
                g = self.streets.geometry(m.name)
                if g is None:
                    continue
                done = False
                for j, o in enumerate(ms):   # (a) a co-mentioned cross street
                    if j == i or o.base == m.base:
                        continue
                    pt = self.streets.intersection(m.name, o.name)
                    if pt is not None:
                        c = self.point_cand(3, "street_anchor", b, m.start, pt, self.street_multi(g, pt))
                        if c:
                            cands.append(c)
                            done = True
                            break
                if done:
                    continue
                best, self_anchor = None, None   # (b) a co-mentioned neighborhood or landmark
                for name, (lon, lat), a_res, (asrc, a0, a1) in anchors:
                    d = g.distance(Point(lon, lat))
                    if (asrc == src and a0 < m.end and m.start < a1) or \
                            re.sub(r" (?:road|rd|corridor|avenue|ave|expressway)$", "", norm(name)) == m.base:
                        # the street's own name matched a corridor alias ("Story Rd", "Blossom Hill"): circular,
                        # so only a last resort after the item cluster
                        if d < ANCHOR_MAX_DEG:
                            self_anchor = (name, Point(lon, lat))
                        continue
                    if d < ANCHOR_MAX_DEG and (best is None or d < best[0]):
                        best = (d, name, Point(lon, lat), a_res)
                if best:
                    pt = nearest_points(g, best[2])[0]
                    bb = "both" if (best[3] and b == "issue") else b
                    c = self.point_cand(3, "street_anchor", bb, m.start, pt, self.street_multi(g, pt), best[1])
                    if c:
                        cands.append(c)
                        continue
                pending.append((m, b, g, self_anchor))   # (c) left for the item-cluster pass
        return cands, pending

    def resolve(self, row: dict) -> tuple[Result, list]:
        cid = str(row["comment_id"])
        title = str(row.get("item_title") or "")
        body = strip_title_lines(clean_ocr(row.get("text") or ""), title)
        subject = clean_ocr(row.get("subject") or "")
        if subject.lower() == "nan":
            subject = ""
        parts = [("body", body), ("subject", subject)]
        title_pl = self.title_places(title)
        district, dsrc = self.stated_district(parts)

        cands, consumed = self.address_cands(cid, parts, row)
        nbs, lms = self.place_mentions(parts, row)
        anchors = []
        field_nb = str(row.get("neighborhood") or "").strip()
        if field_nb and field_nb.lower() != "nan" and row.get("channel") != "letter":
            # user-entered field (email/site); a letter's field is ingest's regex guess, re-derived from text
            ms = find_mentions(field_nb, self.refs.nb_names)
            if ms:
                tid, multi = self.primary_tract(ms[0].canon)
                cands.append(Cand(5, "field", "residence", -1, tid, multi, ms[0].canon,
                                  self.refs.nb_pt.get(ms[0].canon)))
                if self.refs.nb_pt.get(ms[0].canon):
                    anchors.append((ms[0].canon, self.refs.nb_pt[ms[0].canon], True, ("field", -1, -1)))
        for src, m, st, res, ss in lms:
            lat, lon, _ = LANDMARKS[m.canon]
            if lat is None:
                continue
            from shapely.geometry import Point
            b = self.basis(res, m.canon, title_pl, subject, m.canon in {x.canon for x in
                                                                         find_mentions(subject, self.refs.lm_names, 92)})
            c = self.point_cand(2, "landmark", b, m.start, Point(lon, lat), name=m.canon)
            if c:
                cands.append(c)
                anchors.append((m.canon, (lon, lat), res, (src, m.start, m.end)))
        for src, m, st, res, ss in nbs:
            tid, multi = self.primary_tract(m.canon)
            where = "signature" if (src == "body" and m.start >= ss) else src
            b = self.basis(res, m.canon, title_pl, subject, src == "subject")
            cands.append(Cand(5, where, b, m.start, tid, multi, m.canon, self.refs.nb_pt.get(m.canon)))
            if self.refs.nb_pt.get(m.canon):
                anchors.append((m.canon, self.refs.nb_pt[m.canon], res, (src, m.start, m.end)))
        sc, pending = self.street_cands(parts, consumed, anchors, title_pl, subject)
        cands += sc
        z = self.zip_cand(parts, row)
        if z:
            cands.append(z)
        return self.finish(cands, district, dsrc), pending

    def finish(self, cands: list[Cand], district, dsrc) -> Result:
        if not cands:
            if district:
                return Result(precision="district", source=dsrc, district=district, basis="residence")
            return Result()
        c = min(cands, key=lambda c: (c.rank, BASIS_ORDER.get(c.basis, 1), c.pos))
        # council_district describes the resolved place; a stated district is used only when there is no tract
        return Result(c.tract_id, RANK_PRECISION[c.rank], c.source, c.multi,
                      self.refs.tract_district.get(c.tract_id) or district, c.matched_name, c.basis, c.point)

    def anchor_to_cluster(self, pending: list, centroid: tuple) -> Optional[Cand]:
        """Single street with nothing else to pin it: the segment nearest the item's located cluster."""
        from shapely.geometry import Point
        from shapely.ops import nearest_points
        cen = Point(*centroid)
        best = None
        for m, b, g, _ in pending:
            d = g.distance(cen)
            if d < CLUSTER_MAX_DEG and (best is None or d < best[0]):
                best = (d, m, b, g)
        if not best:
            return None
        _, m, b, g = best
        pt = nearest_points(g, cen)[0]
        return self.point_cand(4, "street_anchor", b, m.start, pt, self.street_multi(g, pt))

    def zip_cand(self, parts, row) -> Optional[Cand]:
        z = str(row.get("zip") or "").split(".")[0].strip()
        src = "signature" if row.get("channel") == "letter" else "field"
        cands = [(z, src)] if re.fullmatch(r"9\d{4}", z) else []
        body = dict(parts).get("body", "")
        for line in signature_block(body).split("\n"):
            for m in ZIP_RE.finditer(line):
                cands.append((m.group(1), "signature"))
        for zz, s in cands:
            i = body.find(zz)
            ctx = body[max(0, i - 120):i] if i >= 0 else ""
            if re.search(r"200\s+E\.?\s+Santa\s+Clara", ctx, re.I):   # City Hall recipient block
                continue
            city = re.search(r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s*,?\s*(?:CA|California)\s*,?\s*$", ctx)
            if city and not re.search(r"(?:^| )(?:san ?jose|california)$", norm(city.group(1))):
                continue
            if zz in self.refs.xwalk:
                tid, multi = self.refs.xwalk[zz]
                return Cand(6, s, "residence", 10 ** 6, tid, multi, "", self.refs.tract_pt.get(tid))
        return None


NAMED_BEFORE = re.compile(r"((?:[A-Z][\w'’-]+\s+){0,2}[A-Z][\w'’-]+)\s+(?:(?:Apartments?|Apts\.?|Plaza|Center|data center|"
                          r"Data Center|project|Project|Homes|Village|Towers?)\s*)?[(,]?\s*(?:near|off|by|cerca de|"
                          r"gần)\s+(?:the\s+)?$")
NAME_STOP = {"the", "at", "a", "tenants", "i", "we", "my", "our", "dear", "hello", "hi", "in", "en", "los", "las",
             "apartamentos", "proposed", "approving", "certifying", "oppose", "support"}


def learn_named_places(res: Resolver, rows: list[dict], out: list[Result]) -> dict:
    """'Cedar Court Apartments near Tully Road', 'Terra Verde data center off Gold Street': a named building or
    project (often fictional) is never geocoded by name; when one comment pins it to a real street, the other
    comments on the same item that name it get that comment's point."""
    learned = defaultdict(dict)
    for row, r in zip(rows, out):
        if r.precision != "address" or r.source not in ("street_anchor", "intersection") or not r.point:
            continue
        text = clean_ocr(row.get("text") or "") + "\n" + clean_ocr(row.get("subject") or "")
        for m in find_streets(text, res.streets, res.nb_norms):
            nm = NAMED_BEFORE.search(text[max(0, m.start - 90):m.start])
            if not nm:
                continue
            words = nm.group(1).split()
            while words and norm(words[0]) in NAME_STOP:
                words = words[1:]
            while words and re.fullmatch(r"(?i)apartments?|apts\.?|plaza|center|homes|village|towers?|project", words[-1]):
                words = words[:-1]
            name = norm(" ".join(words))
            typed = bool(re.search(r"(?:Apartments?|Apts|Plaza|Center|data center|project|Homes|Village|Tower)",
                                   nm.group(0), re.I))
            b, t, _ = _street_regex(name)
            if len(name) < 5 or name in res.nb_norms or (t and res.streets.is_street(b) and not typed):
                continue
            learned[row.get("item", "")][name] = r.point
    return learned


CLUSTER_SPREAD_DEG = 0.03   # ~3 km: a cluster anchors only when its members' median distance to it is below this


def resolve_all(res: Resolver, rows: list[dict]) -> list[Result]:
    """Pass 1 per comment. Pass 2, for comments still coarser than address:
      (i)   a named place (building/project) that another comment on the same item pinned to a street;
      (ii)  a single street anchored to the item's located cluster: the segment nearest the centroid of the item's
            other located comments, when that cluster is compact;
      (iii) a single street anchored to its own same-named corridor/area (last resort)."""
    from shapely.geometry import Point
    from shapely.ops import nearest_points
    import statistics
    out, pend = [], []
    for row in rows:
        r, p = res.resolve(row)
        out.append(r)
        pend.append(p)
    pts = defaultdict(list)
    for i, (row, r) in enumerate(zip(rows, out)):
        if r.point and r.precision in ("address", "neighborhood"):
            pts[row.get("item", "")].append((i, r.point))
    street_hit = {}
    for i, (row, r, p) in enumerate(zip(rows, out, pend)):
        if r.precision == "address" or not p:
            continue
        hit = None
        others = [pt for j, pt in pts.get(row.get("item", ""), []) if j != i]
        if others:
            cen = (sum(x for x, _ in others) / len(others), sum(y for _, y in others) / len(others))
            spread = statistics.median(((x - cen[0]) ** 2 + (y - cen[1]) ** 2) ** 0.5 for x, y in others)
            if spread < CLUSTER_SPREAD_DEG:
                hit = res.anchor_to_cluster(p, cen)
                if hit:
                    res.stats["cluster_anchored"] += 1
        if hit is None:
            for m, b, g, sa in p:
                if sa:
                    pt = nearest_points(g, sa[1])[0]
                    hit = res.point_cand(4, "street_anchor", b, m.start, pt, res.street_multi(g, pt), sa[0])
                    if hit:
                        res.stats["self_named_anchor"] += 1
                        break
        if hit:
            street_hit[i] = hit

    def as_result(hit, r):
        return Result(hit.tract_id, "address", hit.source, hit.multi,
                      res.refs.tract_district.get(hit.tract_id) or r.district, hit.matched_name, hit.basis, hit.point)

    mid = [as_result(street_hit[i], r) if i in street_hit else r for i, r in enumerate(out)]
    learned = learn_named_places(res, rows, mid)
    final = list(mid)
    for i, (row, r) in enumerate(zip(rows, mid)):
        if r.precision == "address":
            continue
        title = norm(row.get("item_title") or "")
        text = strip_accents(clean_ocr(row.get("text") or "") + "\n" + clean_ocr(row.get("subject") or ""))
        for name, pt in learned.get(row.get("item", ""), {}).items():
            if name in title:
                continue   # the item's own subject (e.g. the project the agenda item is about) says nothing finer
            mm = re.search(r"(?i)(?<![\w])" + r"\s+".join(map(re.escape, name.split())) + r"(?![\w])", text)
            if mm:
                cue = residence_cue(text, mm.start(), mm.end(), len(text))
                c = res.point_cand(3, "street_anchor", "residence" if cue else "issue", mm.start(), Point(*pt))
                if c:
                    res.stats["named_place_propagated"] += 1
                    final[i] = as_result(c, r)
                    break
    return final


# ------------------------------------------------------------------------------------------- io

def load_hints() -> dict:
    out = {}
    for p in HINT_FILES:
        if p.exists():
            try:
                out.update(json.loads(p.read_text() or "{}"))
            except json.JSONDecodeError:
                pass
    return out


def load_inputs(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for p in paths:
        if not p.exists():
            continue
        d = pd.read_csv(p, dtype=str, keep_default_na=False)
        for c in ["text", "subject", "neighborhood", "zip", "item", "item_title", "channel"]:
            if c not in d.columns:
                d[c] = ""
        d.loc[d.channel == "", "channel"] = p.stem.split("_")[0]
        frames.append(d)
    if not frames:
        sys.exit("no input CSVs found")
    df = pd.concat(frames, ignore_index=True)
    return df.drop_duplicates("comment_id", keep="first")


def coverage(df: pd.DataFrame, loc: pd.DataFrame, n_tracts: int) -> dict:
    m = df[["comment_id", "channel", "item"]].merge(loc, on="comment_id")

    def tiers(g):
        n = len(g)
        c = g.location_precision.value_counts()
        return {"n": n, "tiers": {t: {"count": int(c.get(t, 0)), "share": round(c.get(t, 0) / n, 4) if n else 0}
                                  for t in TIERS},
                "basis": {b: int((g.location_basis == b).sum()) for b in BASES},
                "with_tract": int((g.tract_id != "").sum()),
                "with_tract_share": round((g.tract_id != "").sum() / n, 4) if n else 0}

    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tract_count": n_tracts, **tiers(m),
           "distinct_tracts": int(m.loc[m.tract_id != "", "tract_id"].nunique()),
           "multi_tract": int((m.multi_tract == "true").sum()),
           "by_source": {f"{p}/{s or '-'}": int(n) for (p, s), n in
                         m.groupby(["location_precision", "location_source"]).size().items()},
           "by_basis": {f"{p}/{b or '-'}": int(n) for (p, b), n in
                        m.groupby(["location_precision", "location_basis"]).size().items()},
           "by_channel": {ch: tiers(g) for ch, g in m.groupby("channel")},
           "by_item": {it: tiers(g) for it, g in m.groupby("item")},
           "by_council_district": {str(k): int(v) for k, v in
                                   m.loc[m.council_district != "", "council_district"].value_counts().sort_index()
                                   .items()},
           "by_matched_name": [{"name": k, "count": int(v),
                                "precision": m.loc[m.matched_name == k, "location_precision"].iloc[0]}
                               for k, v in m.loc[m.matched_name != "", "matched_name"].value_counts().items()]}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", action="append", type=Path, help="CSV(s) with comment_id,text[,neighborhood,zip]")
    ap.add_argument("--offline", action="store_true", help="use only cached lookups (no network)")
    ap.add_argument("--out", type=Path, default=OUT_LOC)
    ap.add_argument("--coverage", type=Path, default=OUT_COV)
    a = ap.parse_args(argv)

    refs = load_refs()
    load_crosswalk(refs, a.offline)
    cache, net = Cache(CACHE_PATH), Net(a.offline)
    res = Resolver(refs, make_census_geocoder(refs, cache, net), Streets(net), load_hints())
    df = load_inputs(a.input or DEFAULT_INPUTS)
    recs = df.to_dict("records")
    try:
        results = resolve_all(res, recs)
    finally:
        cache.save()
    rows = [{"comment_id": row["comment_id"], "tract_id": r.tract_id, "location_precision": r.precision,
             "location_source": r.source, "location_basis": r.basis, "multi_tract": "true" if r.multi else "false",
             "council_district": str(r.district) if r.district else "", "matched_name": r.matched_name}
            for row, r in zip(recs, results)]
    loc = pd.DataFrame(rows, columns=OUT_COLS)
    assert not loc.astype(str).apply(lambda c: c.str.contains(HOUSE_RE)).any().any(), "street address in output"
    loc.to_csv(a.out, index=False)
    cov = coverage(df, loc, len(refs.tract_ids))
    a.coverage.parent.mkdir(parents=True, exist_ok=True)
    a.coverage.write_text(json.dumps(cov, indent=1, ensure_ascii=False) + "\n")

    print(f"resolved {len(loc)} comments -> {a.out.relative_to(ROOT) if a.out.is_relative_to(ROOT) else a.out}")
    for t in TIERS:
        c = cov["tiers"][t]
        print(f"  {t:13s} {c['count']:4d}  {c['share']:.1%}")
    for ch, v in cov["by_channel"].items():
        tiers_s = " ".join(f"{t}={v['tiers'][t]['count']}" for t in TIERS)
        print(f"  [{ch}] n={v['n']} {tiers_s} | with tract {v['with_tract']} ({v['with_tract_share']:.1%}) "
              f"| basis {v['basis']}")
    print(f"  sources: {cov['by_source']}")
    print(f"  network calls={net.calls} failures={net.failures} stats={dict(res.stats)}")


if __name__ == "__main__":
    main()
