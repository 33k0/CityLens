"""resolve_locations tests on small synthetic fixtures. No network: the geocoder and the street-intersection lookup
are injected fakes, and point-in-polygon is monkeypatched."""
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import resolve_locations as rl  # noqa: E402

T_DOWNTOWN_BIG, T_DOWNTOWN_SMALL, T_WG, T_EAST, T_LANDMARK, T_ZIP_A, T_ZIP_B = (
    "06085000001", "06085000002", "06085000003", "06085000004", "06085000005", "06085000006", "06085000007")

NB = pd.DataFrame([
    {"name": "Downtown", "aliases": "Downtown San Jose", "lat": "", "lon": "",
     "tract_ids": f"{T_DOWNTOWN_SMALL}|{T_DOWNTOWN_BIG}", "source": "sjgis"},
    {"name": "Willow Glen", "aliases": "WG", "lat": "", "lon": "", "tract_ids": T_WG, "source": "hand"},
    {"name": "Berryessa", "aliases": "", "lat": "", "lon": "", "tract_ids": T_EAST, "source": "hand"},
    {"name": "Story Road", "aliases": "Story Rd", "lat": "", "lon": "", "tract_ids": T_EAST, "source": "hand"},
    # generic SJ GIS names that must never match on their own
    {"name": "Commercial", "aliases": "", "lat": "", "lon": "", "tract_ids": T_EAST, "source": "sjgis"},
    {"name": "Union", "aliases": "", "lat": "", "lon": "", "tract_ids": T_EAST, "source": "sjgis"},
    {"name": "Estates", "aliases": "", "lat": "", "lon": "", "tract_ids": T_EAST, "source": "sjgis"},
    {"name": "Alma", "aliases": "", "lat": "", "lon": "", "tract_ids": T_EAST, "source": "sjgis"},
])
POP = {T_DOWNTOWN_BIG: 9000, T_DOWNTOWN_SMALL: 1000, T_WG: 4000, T_EAST: 5000, T_LANDMARK: 3000, T_ZIP_A: 6000,
       T_ZIP_B: 2000}


@pytest.fixture
def refs(monkeypatch):
    r = rl.Refs(tract_ids=set(POP), pop=POP, tract_district={t: 3 for t in POP})
    r.tract_district[T_WG] = 6
    rl.add_names(r, NB, words={"commercial", "union", "estates", "alma"})
    r.xwalk = {"95125": (T_ZIP_A, True), "95037": (T_ZIP_B, False)}
    monkeypatch.setattr(rl, "point_tract", lambda refs, lat, lon: T_LANDMARK if lat else None)
    return r


class Fakes:
    def __init__(self):
        self.geocoded, self.intersected = [], []

    def geocode(self, q):
        self.geocoded.append(q)
        return T_WG if "Lincoln" in q else None

    def intersect(self, a, b):
        self.intersected.append((a, b))
        return T_EAST if {rl._street_regex(a)[0], rl._street_regex(b)[0]} == {"story", "king"} else None


def resolve(refs, text, hints=None, **row):
    f = Fakes()
    res = rl.Resolver(refs, f.geocode, f.intersect, hints or {})
    base = {"comment_id": row.pop("comment_id", "X1"), "text": text, "subject": "", "neighborhood": "", "zip": "",
            "channel": "letter", "item_title": "Some agenda item"}
    base.update(row)
    return res.resolve(base), f


# --- address tier

def test_signature_hint_address_geocodes(refs):
    hints = {"X1": {"address": "1234 Lincoln Ave", "cross_street": "", "zip": "95125"}}
    r, f = resolve(refs, "Please vote yes.\nSincerely,\nA Resident", hints)
    assert (r.precision, r.source, r.tract_id) == ("address", "signature", T_WG)
    assert f.geocoded and f.geocoded[0].endswith("San Jose, CA 95125")
    assert r.district == 6 and r.matched_name == ""


def test_body_address_block_geocodes_but_city_hall_and_other_cities_do_not(refs):
    r, f = resolve(refs, "Sincerely,\nOrg Name\n55 Lincoln Ave\nSan Jose, CA 95125")
    assert (r.precision, r.source) == ("address", "body")
    r, f = resolve(refs, "San José City Council\n200 E. Santa Clara Street\nSan José, CA 95113\nDear Council,")
    assert r.precision == "none" and not f.geocoded
    r, f = resolve(refs, "Thanks,\nWes\n986 Lincoln Street | San Francisco, CA 94103")
    assert r.precision == "none" and not f.geocoded


def test_address_inside_a_sentence_is_not_the_writer(refs):
    r, f = resolve(refs, "The RV lot at 1300 Lincoln Ave is a bad idea.")
    assert r.precision == "none" and not f.geocoded


def test_intersection_uses_street_lookup(refs):
    r, f = resolve(refs, "I live near the crosswalk at Story and King and I oppose this.")
    assert (r.precision, r.source, r.tract_id) == ("address", "intersection", T_EAST)
    assert f.intersected[0] == ("Story", "King")


def test_landmark_needs_a_proximity_cue(refs):
    r, _ = resolve(refs, "My neighbors near Kelley Park got a huge rent hike.")
    assert (r.precision, r.source, r.matched_name) == ("address", "landmark", "Kelley Park")
    r, _ = resolve(refs, "He is a proud graduate of San Jose State University.")
    assert r.precision == "none"


# --- neighborhood tier

def test_neighborhood_residence_cue_picks_most_populous_tract(refs):
    r, _ = resolve(refs, "I have lived in downtown San Jose for 20 years and support this.")
    assert (r.precision, r.tract_id, r.multi, r.matched_name) == ("neighborhood", T_DOWNTOWN_BIG, True, "Downtown")


def test_token_aware_and_fuzzy_in_sentence(refs):
    r, _ = resolve(refs, "As a homeowner in Wilow Glen, I am opposed.")
    assert (r.precision, r.matched_name, r.multi) == ("neighborhood", "Willow Glen", False)


def test_field_trusted_for_non_letter_channels_only(refs):
    r, _ = resolve(refs, "Fix the streets.", neighborhood="Willow Glen", channel="email")
    assert (r.precision, r.source) == ("neighborhood", "field")
    r, _ = resolve(refs, "Fix the streets.", neighborhood="Willow Glen", channel="letter")
    assert r.precision == "none"   # a letter's field is ingest's regex guess; re-derived from text instead


def test_item_title_is_not_a_location(refs):
    title = "Grant agreement for a parking program at 1300 Berryessa Road and Story Road corridor lighting"
    text = ("Item 3.2 Grant agreement for a parking program at 1300 Berryessa Road\n"
            "I oppose the 1300 Berryessa Road site. The lights along Story Road and Berryessa matter.")
    r, f = resolve(refs, text, item_title=title)
    assert r.precision == "none" and not f.geocoded
    # but a first-person proximity statement about the same place still counts
    r, _ = resolve(refs, "Our kids walk home in the dark near Story Rd.", item_title=title)
    assert (r.precision, r.matched_name) == ("neighborhood", "Story Road")


def test_bare_or_org_mentions_are_rejected(refs):
    for t in ["Downtown San Jose needs a leader.",
              "Two lawsuits in Oregon and Washington D.C. argue otherwise.",
              "I serve as a trustee of the Berryessa Union School District."]:
        r, _ = resolve(refs, t)
        assert r.precision == "none", t


def test_generic_names_excluded(refs):
    names = {n for n, *_ in refs.nb_names}
    assert not names & {"commercial", "union", "estates", "alma"}
    r, _ = resolve(refs, "I live in a commercial zone near the Union hall in the Estates on Alma.")
    assert r.precision == "none"
    assert rl.eligible_name("Commercial", curated=True, words={"commercial"})   # curated names are allowed


def test_negated_residence(refs):
    r, _ = resolve(refs, "I don't live in Willow Glen but I support this.")
    assert r.precision == "none"


# --- zip and district tiers

def test_zip_from_signature_uses_crosswalk(refs):
    r, _ = resolve(refs, "Please vote yes.\nSincerely\n[name removed]\nSan Jose, California 95125")
    assert (r.precision, r.source, r.tract_id, r.multi) == ("zip", "signature", T_ZIP_A, True)
    r, _ = resolve(refs, "Please vote yes.\nSincerely\n[name removed]\nMorgan Hill, California 95037")
    assert r.precision == "none"   # a ZIP that names another city is not a San José location


def test_stated_district_only(refs):
    r, _ = resolve(refs, "I am a resident of District 5 and I support the memo.")
    assert (r.precision, r.tract_id, r.district) == ("district", "", 5)
    r, _ = resolve(refs, "Please appoint her to the District 3 seat.", item_title="Interim appointment to District 3")
    assert r.precision == "none" and r.district is None


def test_stated_district_overrides_tract_overlay(refs):
    r, _ = resolve(refs, "I'm a District 3 resident. I have lived in Willow Glen for years.")
    assert r.tract_id == T_WG and r.district == 3


# --- privacy

def test_cache_keys_are_hashes_and_output_has_no_street_address(refs, tmp_path, monkeypatch):
    c = rl.Cache(tmp_path / "cache.json")
    c.put("census|1234 lincoln ave, san jose, ca", "06085000003", True, "census_onelineaddress")
    c.save()
    raw = (tmp_path / "cache.json").read_text()
    assert "lincoln" not in raw.lower() and re.search(r'"[0-9a-f]{64}"', raw)

    f = Fakes()
    rows = [{"comment_id": f"C{i}", "text": t, "subject": "", "neighborhood": "", "zip": "", "channel": "letter",
             "item_title": ""} for i, t in enumerate([
                 "Sincerely,\nOrg\n55 Lincoln Ave\nSan Jose, CA 95125",
                 "I live near the crosswalk at Story and King.",
                 "I have lived in Willow Glen for years."])]
    res = rl.Resolver(refs, f.geocode, f.intersect, {})
    out = pd.DataFrame([{"comment_id": r["comment_id"], **vars(res.resolve(r))} for r in rows])
    blob = out.astype(str).to_csv(index=False)
    assert not rl.HOUSE_RE.search(blob)
    assert "Lincoln" not in blob and "Story and King" not in blob


def test_real_locations_csv_has_no_house_numbers():
    p = rl.OUT_LOC
    if not p.exists():
        pytest.skip("run scripts/resolve_locations.py first")
    blob = p.read_text()
    assert not rl.HOUSE_RE.search(blob)
    df = pd.read_csv(p, dtype=str, keep_default_na=False)
    assert list(df.columns) == rl.OUT_COLS
    assert set(df.location_precision) <= set(rl.TIERS)
    assert (df.loc[df.location_precision.isin(["district", "none"]), "tract_id"] == "").all()
