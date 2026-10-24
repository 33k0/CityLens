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
OUT_COLS = ["comment_id", "tract_id", "location_precision", "location_source", "multi_tract", "council_district",
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
                    "noble", "hammer", "glider", "checkers", "majestic", "cypress", "sundown", "mulberry", "southwest",
                    "reed", "alma", "monroe", "toyon", "cahalan", "carden", "kirk", "muir", "parma", "hayes", "lido",
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
                 "southwest", "park", "naglee", "the alameda", "race", "lincoln", "delmas", "bird", "minnesota"}

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
    r"raised|here)\b(?:\s+\w+){0,3}\s+(?:in|at|near|by|on|of|off)\s+(?:the\s+|our\s+|my\s+)?$|"
    r"\b(?:vivo|vivimos|resido)\s+(?:en|cerca de|cerca del)\s+(?:la zona de\s+)?$|"
    r"\b(?:mi|nuestro)\s+(?:vecindario|barrio)\s+(?:en|cerca de|cerca del)\s+$|"
    r"\b(?:tôi|chúng tôi)\b[^.\n]{0,40}\b(?:gần|ở khu|ở)\s+$", re.I)
CUE_AFTER_PLACE = re.compile(r"^\s*(?:neighbou?rhood|area)\b", re.I)
CUE_AFTER_PERSON = re.compile(r"^\s*(?:resident|residents|homeowner|homeowners|neighbou?rs?|renter|renters|tenant|"
                              r"tenants|native|family|families|block)\b", re.I)
NEAR_BEFORE = re.compile(r"\b(?:near|by|around|next to|across from|across the street from|behind|along|outside|"
                         r"in front of|close to|walking distance (?:of|from|to)|blocks? from|cerca de|cerca del|"
                         r"junto a|junto al|gần)\s+(?:the\s+|el\s+|la\s+)?(?:parque\s+)?$", re.I)
PERSONAL_CUE = re.compile(r"\b(?:I|I'm|live|living|lived|my|our|near|home|walk|walking|neighbou?rs?|me|we)\b", re.I)
WRITING = re.compile(r"\b(?:I'm|I am|I)\s+(?:writing|write)\b[^.]*", re.I)
MY_BEFORE = re.compile(r"\b(?:my|our)\s+(?:\w+\s+){0,1}$", re.I)
ORG_AFTER = re.compile(r"^\s*(?:union|unified|elementary|school district|community college|college|hall of fame|"
                       r"square|d\.?\s?c\b|high school|foundation|county|state\b|university|trustee)", re.I)
ORG_BEFORE = re.compile(r"\b(?:somos)\s*$", re.I)
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
NAME = (r"(?:[NSEW]\.?\s+)?(?:\d{1,2}(?:st|nd|rd|th)|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
        r"(?:\s+(?:" + STREET_SUFFIX + r"))?\.?")
INTER_RE = re.compile(r"\b(?:corner of|intersection of|at|near|by|on|off|around|cross|crossing)\s+(?:the\s+)?(?:corner of\s+)?"
                      r"(" + NAME + r")\s*(?:and|&|/|@)\s*(" + NAME + r")")
INTER_AMP = re.compile(r"(?<![\w])(" + NAME + r")\s*(?:&|/)\s*(" + NAME + r")")


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
    hit = refs.tract_geom[refs.tract_geom.contains(p)]
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


def _street_regex(name: str) -> tuple[str, Optional[str], str]:
    """'N First St' -> (base 'first', type 'st', direction 'n')."""
    n = norm(name).replace(".", "")
    toks = n.split()
    d = toks[0] if toks and toks[0] in {"n", "s", "e", "w", "north", "south", "east", "west"} and len(toks) > 1 else ""
    if d:
        toks = toks[1:]
    typ = None
    if len(toks) > 1:
        t = TYPE_CANON.get(toks[-1], toks[-1])
        if t in set(TYPE_CANON.values()) | {"st", "ave", "rd", "blvd", "dr", "ct", "ln", "pl", "way", "expy", "pkwy",
                                            "hwy", "cir", "ter", "sq"}:
            typ = t
            toks = toks[:-1]
    ordmap = {"first": "1st", "second": "2nd", "third": "3rd", "fourth": "4th", "fifth": "5th", "sixth": "6th",
              "seventh": "7th", "eighth": "8th", "ninth": "9th", "tenth": "10th", "eleventh": "11th"}
    base = " ".join(ordmap.get(t, t) for t in toks)
    return base, typ, d[:1]


def make_intersection_lookup(refs: Refs, cache: Cache, net: Net) -> Callable[[str, str], Optional[str]]:
    from shapely.geometry import MultiPoint, Point, shape
    from shapely.ops import unary_union

    def fetch(base: str) -> Optional[list]:
        feats, offset = [], 0
        b = base.upper().replace("'", "''")
        where = f"UPPER(FULLNAME) LIKE '{b} %' OR UPPER(FULLNAME) LIKE '% {b} %' OR UPPER(FULLNAME) = '{b}'"
        while True:
            js = net.get_json(f"{STREETS_LAYER}/query", {"where": where, "outFields": "FULLNAME", "outSR": 4326,
                                                         "f": "geojson", "resultOffset": offset,
                                                         "resultRecordCount": 2000})
            if js is None:
                return None
            fs = js.get("features") or []
            feats += fs
            if len(fs) < 2000 or offset > 10000:
                return feats
            offset += 2000

    def groups(feats, base, typ, d) -> dict:
        out = defaultdict(list)
        pat = re.compile(r"^(?:([nsew]) )?" + re.escape(base) + r"(?: ([a-z]+))?(?: [nsew])?$")
        for f in feats:
            fn = norm(f["properties"].get("FULLNAME", "")).replace(".", "")
            m = pat.match(fn)
            if not m or not f.get("geometry"):
                continue
            t = m.group(2) or ""
            if typ and t != typ:
                continue
            if d and m.group(1) and m.group(1) != d:
                continue
            out[t].append(shape(f["geometry"]))
        return {t: unary_union(g) for t, g in out.items()}

    def lookup(a: str, b: str) -> Optional[str]:
        pa, pb = _street_regex(a), _street_regex(b)
        if not pa[0] or not pb[0] or pa[0] == pb[0]:
            return None
        key = "intersection|" + "|".join(sorted([" ".join(filter(None, pa)), " ".join(filter(None, pb))]))
        c = cache.get(key)
        if c is not None:
            return c["tract_id"] or None
        fa, fb = fetch(pa[0]), fetch(pb[0])
        if fa is None or fb is None:
            return None
        ga, gb = groups(fa, *pa), groups(fb, *pb)
        best_pts = []
        for major_only in (True, False):
            pts = []
            for ta, geo_a in ga.items():
                for tb, geo_b in gb.items():
                    if major_only and not (ta in MAJOR_TYPES and tb in MAJOR_TYPES):
                        continue
                    inter = geo_a.intersection(geo_b)
                    if inter.is_empty:
                        if geo_a.distance(geo_b) < 0.00015:   # ~15 m: centerlines that just miss
                            from shapely.ops import nearest_points
                            pts.append(nearest_points(geo_a, geo_b)[0])
                        continue
                    pts += [g.centroid for g in getattr(inter, "geoms", [inter])]
            if pts:
                best_pts = pts
                break
        tid = None
        if best_pts:
            mp = MultiPoint(best_pts)
            minx, miny, maxx, maxy = mp.bounds
            if max(maxx - minx, maxy - miny) < 0.01:   # one place (~1 km); two far-apart crossings are ambiguous
                cen = mp.centroid
                tid = point_tract(refs, cen.y, cen.x)
        cache.put(key, tid, bool(best_pts), "sjgis_streets_intersection")
        return tid
    return lookup


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
                if s >= threshold and min(fuzz.ratio(x, y) for x, y in zip(cand.split(), nn.split())) < 75:
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
    """3 residence cue, 2 signature line, 1 locative preposition, 0 reject."""
    before = text[max(0, m.start - 70):m.start]
    after = text[m.end:m.end + 40]
    line_before = before.split("\n")[-1]
    if ORG_AFTER.match(after) or ORG_BEFORE.search(before) or \
            (SUFFIX_AFTER.match(after) and not MY_BEFORE.search(line_before)):   # "Almaden Rd" is a street
        return 0
    sent = sentence_around(text, m.start, m.end)
    if NEGATION.search(sent):
        return 0
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


class Resolver:
    def __init__(self, refs: Refs, geocode: Callable[[str], Optional[str]],
                 intersect: Callable[[str, str], Optional[str]], hints: dict):
        self.refs, self.geocode, self.intersect, self.hints = refs, geocode, intersect, hints
        self.stats = Counter()

    # -- helpers
    def primary_tract(self, nb: str) -> tuple[str, bool]:
        tids = self.refs.nb_tracts[nb]
        best = max(tids, key=lambda t: self.refs.pop.get(t, 0))
        return best, len(tids) > 1

    def title_places(self, title: str) -> set:
        t = title or ""
        names = {m.canon for m in find_mentions(t, self.refs.nb_names)}
        names |= {m.canon for m in find_mentions(t, self.refs.lm_names, 90)}
        streets = {_street_regex(m.group(0))[0] for m in
                   re.finditer(r"(?:[NSEW]\.?\s+)?(?:\d{1,2}(?:st|nd|rd|th)|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
                               r"(?:\s+(?:" + STREET_SUFFIX + r"))?", t)}
        addrs = {norm(m.group(0)) for m in HOUSE_RE.finditer(t)}
        return names | {"street:" + s for s in streets} | {"addr:" + a for a in addrs}

    def stated_district(self, parts: list[tuple[str, str]], title_pl: set) -> tuple[Optional[int], str]:
        for src, t in parts:
            for p in DISTRICT_PATTERNS:
                m = p.search(t)
                if m:
                    g = m.group(1).lower()
                    return (NUM_WORDS.get(g) or int(g)), src
        return None, ""

    # -- tiers
    def tier_address(self, cid: str, parts: list[tuple[str, str]], title_pl: set, row: dict) -> Optional[Result]:
        body = dict(parts).get("body", "")
        # 1a. signature hints from ingest (raw, gitignored)
        h = self.hints.get(cid) or {}
        cands = []
        if h.get("address"):
            cands.append(("signature", h["address"], h.get("zip", "")))
        for src, t in parts:
            for m in HOUSE_RE.finditer(t):
                after, before = t[m.end():m.end() + 90], t[max(0, m.start() - 40):m.start()]
                blk = CITY_AFTER.match(after)
                if not blk and not ADDR_CUE_BEFORE.search(before):
                    continue   # an address in a sentence is usually the project site, not the writer
                cands.append(("body" if src == "body" else src, m.group(0), (blk.group(2) or "") if blk else ""))
        seen = set()
        for src, addr, z in cands:
            a = re.sub(r"\s+", " ", addr).strip().rstrip(".")
            if norm(a) in seen:
                continue
            seen.add(norm(a))
            if CITY_HALL.match(a) or "addr:" + norm(a) in title_pl:
                self.stats["address_skipped_cityhall_or_title"] += 1
                continue
            city, zip_ = "San Jose", z
            i = body.find(a.split()[0] + " " + a.split()[1]) if len(a.split()) > 1 else -1
            if i >= 0:
                blk = CITY_AFTER.match(body[i + len(a): i + len(a) + 90])
                if blk:
                    city = blk.group(1)
                    zip_ = blk.group(2) or zip_
            if not re.search(r"(?:^| )san ?jose$", norm(city)):
                self.stats["address_outside_sj"] += 1
                continue
            q = f"{a}, San Jose, CA" + (f" {zip_}" if zip_ else "")
            tid = self.geocode(q)
            if tid:
                if h.get("address") and norm(a) == norm(h["address"]):
                    src = "signature"
                return Result(tid, "address", src)
        # 1b. intersections
        for src, t in parts:
            for rx in (INTER_RE, INTER_AMP):
                for m in rx.finditer(t):
                    a, b = m.group(1), m.group(2)
                    ba, bb = _street_regex(a)[0], _street_regex(b)[0]
                    has_sfx = lambda s: bool(re.search(r"\b(?:" + STREET_SUFFIX + r")\.?$", s, re.I)) or \
                        bool(re.match(r"^(?:[NSEW]\.?\s+)?\d", s))
                    if not ((ba in KNOWN_STREETS or has_sfx(a) or ba in {"1st", "2nd", "3rd", "4th", "5th", "6th",
                                                                       "7th", "8th", "9th", "10th", "11th"})
                            and (bb in KNOWN_STREETS or has_sfx(b) or re.match(r"^\d", bb))):
                        continue
                    sent = sentence_around(t, m.start(), m.end())
                    in_title = {"street:" + ba, "street:" + bb} <= title_pl
                    near = t[max(0, m.start() - 60):m.start()]
                    if NEGATION.search(sent) or (in_title and not PERSONAL_CUE.search(near)):
                        continue
                    tid = self.intersect(a, b)
                    if tid:
                        return Result(tid, "address", "intersection")
        # 1c. landmarks (exact / near-exact name)
        for src, t in parts:
            sig_start = t.find(signature_block(t)) if signature_block(t) else len(t)
            for m in find_mentions(t, self.refs.lm_names, 92):
                lat, lon, _ = LANDMARKS[m.canon]
                if lat is None or (m.canon in title_pl and mention_strength(t, m, sig_start) < 3):
                    continue
                before = t[max(0, m.start - 60):m.start].split("\n")[-1]
                in_sig = m.start >= sig_start and signature_line(
                    t[t.rfind("\n", 0, m.start) + 1:(t.find("\n", m.end) if t.find("\n", m.end) >= 0 else len(t))], m)
                if not (NEAR_BEFORE.search(before) or CUE_RESIDE_BEFORE.search(before) or in_sig) or \
                        NEGATION.search(sentence_around(t, m.start, m.end)):
                    continue   # "graduate of SJSU", "development of Diridon Station" say nothing about where
                tid = point_tract(self.refs, lat, lon)
                if tid:
                    return Result(tid, "address", "landmark", matched_name=m.canon)
        return None

    def tier_neighborhood(self, parts: list[tuple[str, str]], title_pl: set, row: dict) -> Optional[Result]:
        field_nb = str(row.get("neighborhood") or "").strip()
        trust_field = row.get("channel") != "letter"   # letters' field is a regex guess by ingest; re-derived here
        if field_nb and field_nb.lower() != "nan" and trust_field:
            ms = find_mentions(field_nb, self.refs.nb_names)
            if ms:
                tid, multi = self.primary_tract(ms[0].canon)
                return Result(tid, "neighborhood", "field", multi, matched_name=ms[0].canon)
        best = None
        for src, t in parts:
            sig = signature_block(t) if src == "body" else ""
            sig_start = t.rfind(sig) if sig else len(t)
            for m in find_mentions(t, self.refs.nb_names):
                s = mention_strength(t, m, sig_start)
                corridor = _street_regex(m.canon)[0] if re.search(r"(?i)\b(road|avenue|expressway|corridor)\b",
                                                                   m.canon) else ""
                corridor = re.sub(r" (road|avenue|expressway|corridor)$", "", corridor)
                if (m.canon in title_pl or (corridor and "street:" + corridor in title_pl)) and s < 3:
                    continue
                if s == 0:
                    continue
                where = "signature" if (src == "body" and m.start >= sig_start) else src
                if best is None or s > best[0]:
                    best = (s, m.canon, where)
        if best:
            tid, multi = self.primary_tract(best[1])
            return Result(tid, "neighborhood", best[2], multi, matched_name=best[1])
        return None

    def tier_zip(self, parts: list[tuple[str, str]], row: dict) -> Optional[Result]:
        z = str(row.get("zip") or "").split(".")[0].strip()
        src = "signature" if row.get("channel") == "letter" else "field"
        cands = [(z, src)] if re.fullmatch(r"9\d{4}", z) else []
        body = dict(parts).get("body", "")
        sig = signature_block(body)
        for line in sig.split("\n"):
            for m in ZIP_RE.finditer(line):
                cands.append((m.group(1), "signature"))
        for zz, s in cands:
            # recipient block ("200 E Santa Clara St, San Jose, CA 95113") is City Hall, not the writer
            i = body.find(zz)
            ctx = body[max(0, i - 120):i] if i >= 0 else ""
            if re.search(r"200\s+E\.?\s+Santa\s+Clara", ctx, re.I):
                continue
            city = re.search(r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s*,?\s*(?:CA|California)\s*,?\s*$", ctx)
            if city and not re.search(r"(?:^| )(?:san ?jose|california)$", norm(city.group(1))):
                continue
            if zz in self.refs.xwalk:
                tid, multi = self.refs.xwalk[zz]
                return Result(tid, "zip", s, multi)
        return None

    def resolve(self, row: dict) -> Result:
        cid = str(row["comment_id"])
        title = str(row.get("item_title") or "")
        body = strip_title_lines(clean_ocr(row.get("text") or ""), title)
        subject = clean_ocr(row.get("subject") or "")
        if subject.lower() == "nan":
            subject = ""
        parts = [("body", body), ("subject", subject)]
        title_pl = self.title_places(title)
        district, dsrc = self.stated_district(parts, title_pl)
        r = (self.tier_address(cid, parts, title_pl, row) or self.tier_neighborhood(parts, title_pl, row)
             or self.tier_zip(parts, row))
        if r is None:
            r = Result(precision="district", source=dsrc, district=district) if district else Result()
        else:
            r.district = district or self.refs.tract_district.get(r.tract_id)
        return r


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
                "with_tract": int((g.tract_id != "").sum()),
                "with_tract_share": round((g.tract_id != "").sum() / n, 4) if n else 0}

    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tract_count": n_tracts, **tiers(m),
           "distinct_tracts": int(m.loc[m.tract_id != "", "tract_id"].nunique()),
           "multi_tract": int((m.multi_tract == "true").sum()),
           "by_source": {f"{p}/{s or '-'}": int(n) for (p, s), n in
                         m.groupby(["location_precision", "location_source"]).size().items()},
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
    ap.add_argument("--offline", action="store_true", help="use only data/geocode_cache.json (no network)")
    ap.add_argument("--out", type=Path, default=OUT_LOC)
    ap.add_argument("--coverage", type=Path, default=OUT_COV)
    a = ap.parse_args(argv)

    refs = load_refs()
    load_crosswalk(refs, a.offline)
    cache, net = Cache(CACHE_PATH), Net(a.offline)
    res = Resolver(refs, make_census_geocoder(refs, cache, net), make_intersection_lookup(refs, cache, net),
                   load_hints())
    df = load_inputs(a.input or DEFAULT_INPUTS)
    rows = []
    try:
        for row in df.to_dict("records"):
            r = res.resolve(row)
            rows.append({"comment_id": row["comment_id"], "tract_id": r.tract_id, "location_precision": r.precision,
                         "location_source": r.source, "multi_tract": "true" if r.multi else "false",
                         "council_district": str(r.district) if r.district else "", "matched_name": r.matched_name})
    finally:
        cache.save()
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
        print(f"  [{ch}] n={v['n']} with tract {v['with_tract']} ({v['with_tract_share']:.1%})")
    print(f"  sources: {cov['by_source']}")
    print(f"  network calls={net.calls} failures={net.failures} stats={dict(res.stats)}")


if __name__ == "__main__":
    main()
