"""resolve_locations tests on small synthetic fixtures. No network: the Census geocoder is a fake, and the street
source is a synthetic grid fed through the real Streets intersection/anchoring code."""
import re
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import resolve_locations as rl  # noqa: E402

# 2x2 grid of tracts, each 0.02 deg square, covering lon -121.90..-121.86, lat 37.30..37.34
TA, TB, TC, TD = "06085000001", "06085000002", "06085000003", "06085000004"   # SW, SE, NW, NE
TRACTS = {TA: box(-121.90, 37.30, -121.88, 37.32), TB: box(-121.88, 37.30, -121.86, 37.32),
          TC: box(-121.90, 37.32, -121.88, 37.34), TD: box(-121.88, 37.32, -121.86, 37.34)}
POP = {TA: 4000, TB: 9000, TC: 1000, TD: 5000}

STREETS = {   # base -> (FULLNAME, coordinates)
    "story": ("Story Rd", [(-121.90, 37.305), (-121.86, 37.305)]),
    "king": ("S King Rd", [(-121.885, 37.30), (-121.885, 37.34)]),
    "tully": ("Tully Rd", [(-121.90, 37.335), (-121.86, 37.335)]),
    "alma": ("W Alma Ave", [(-121.90, 37.325), (-121.86, 37.325)]),
    "gold": ("Gold St", [(-121.865, 37.30), (-121.865, 37.34)]),
    "101": ("101", [(-121.90, 37.30), (-121.86, 37.34)]),
    "cedar": ("Cedar Ct", [(-121.00, 37.00), (-121.00, 37.01)]),   # a real-looking street far away
    "lincoln": ("Lincoln Ave", [(-121.895, 37.30), (-121.895, 37.34)]),
    "5th": ("N 5th St", [(-121.87, 37.30), (-121.87, 37.34)]),
    "william": ("E William St", [(-121.90, 37.315), (-121.86, 37.315)]),
}

NB = pd.DataFrame([
    {"name": "Downtown", "aliases": "Downtown San Jose", "lat": "37.33", "lon": "-121.87",
     "tract_ids": f"{TC}|{TD}", "source": "sjgis"},
    {"name": "Willow Glen", "aliases": "WG", "lat": "37.31", "lon": "-121.895", "tract_ids": TA, "source": "hand"},
    {"name": "Washington-Guadalupe", "aliases": "Washington", "lat": "37.327", "lon": "-121.875",
     "tract_ids": TD, "source": "sjgis"},
    {"name": "Alviso", "aliases": "", "lat": "37.31", "lon": "-121.862", "tract_ids": TB, "source": "sjgis"},
    {"name": "Story Road", "aliases": "Story Rd", "lat": "37.305", "lon": "-121.875", "tract_ids": TB,
     "source": "hand"},
    {"name": "Commercial", "aliases": "", "lat": "", "lon": "", "tract_ids": TB, "source": "sjgis"},
    {"name": "Union", "aliases": "", "lat": "", "lon": "", "tract_ids": TB, "source": "sjgis"},
    {"name": "Estates", "aliases": "", "lat": "", "lon": "", "tract_ids": TB, "source": "sjgis"},
])


class GridStreets(rl.Streets):
    """The real Streets logic over a synthetic grid (no network, no disk)."""

    def __init__(self):
        self.net, self._feats = None, {}
        self.bases = {b: {rl._street_regex(n)[1] or ""} for b, (n, _) in STREETS.items()}

    def _features(self, base):
        if base not in STREETS:
            return None
        n, coords = STREETS[base]
        return [{"properties": {"FULLNAME": n}, "geometry": {"type": "LineString", "coordinates": coords}}]


@pytest.fixture
def refs():
    gdf = gpd.GeoDataFrame({"tract_id": list(TRACTS)}, geometry=list(TRACTS.values()), crs=4326)
    r = rl.Refs(tract_ids=set(POP), pop=POP, tract_district={TA: 3, TB: 7, TC: 3, TD: 6}, tract_geom=gdf)
    r.tract_pt = {t: (g.centroid.x, g.centroid.y) for t, g in TRACTS.items()}
    rl.add_names(r, NB, words={"commercial", "union", "estates"})
    r.xwalk = {"95125": (TA, True), "95037": (TB, False)}
    return r


class Geo:
    def __init__(self):
        self.calls = []

    def __call__(self, q):
        self.calls.append(q)
        return TA if "Lincoln" in q else None


def row(text, cid="X1", **kw):
    base = {"comment_id": cid, "text": text, "subject": "", "neighborhood": "", "zip": "", "channel": "email",
            "item": "ITEM", "item_title": "Some agenda item"}
    base.update(kw)
    return base


def resolve(refs, text, hints=None, **kw):
    g = Geo()
    res = rl.Resolver(refs, g, GridStreets(), hints or {})
    r, _ = res.resolve(row(text, **kw))
    return r, g


def tract_at(lon, lat):
    return next(t for t, g in TRACTS.items() if g.covers(__import__("shapely").geometry.Point(lon, lat)))


# --- address tier: house numbers

def test_signature_hint_address_is_residence(refs):
    hints = {"X1": {"address": "1234 Lincoln Ave", "cross_street": "", "zip": "95125"}}
    r, g = resolve(refs, "Please vote yes.\nSincerely,\nA Resident", hints, channel="letter")
    assert (r.precision, r.source, r.tract_id, r.basis) == ("address", "signature", TA, "residence")
    assert g.calls[0].endswith("San Jose, CA 95125") and r.matched_name == ""


def test_org_letterhead_is_residence_project_site_is_issue(refs):
    r, _ = resolve(refs, "Sincerely,\nOrg Name\n55 Lincoln Ave\nSan Jose, CA 95125", channel="letter")
    assert (r.precision, r.source, r.basis) == ("address", "body", "residence")
    r, g = resolve(refs, "The RV lot at 1300 Lincoln Ave is a bad idea.", channel="letter")
    assert (r.precision, r.basis) == ("address", "issue") and g.calls


def test_city_hall_and_other_cities_are_skipped(refs):
    r, g = resolve(refs, "San José City Council\n200 E. Santa Clara Street\nSan José, CA 95113\nDear Council,")
    assert r.precision == "none" and not g.calls
    r, g = resolve(refs, "Thanks,\nWes\n986 Lincoln Street | San Francisco, CA 94103")
    assert r.precision == "none" and not g.calls


# --- intersections and ranges

@pytest.mark.parametrize("text", [
    "The crosswalk at Story and King is pitch black.",
    "Attaching a night photo of King & Story with every light out.",
    "Blackouts on the Story/King corridor again.",
    "Đèn đường khu Story/King tắt nhiều tuần rồi.",
    "Fix the lights on Story Road and King Road.",
])
def test_intersection_forms(refs, text):
    r, _ = resolve(refs, text)
    assert (r.precision, r.source, r.tract_id) == ("address", "intersection", tract_at(-121.885, 37.305))


def test_intersection_basis(refs):
    r, _ = resolve(refs, "Hi, I live near 5th and William downtown. Every rain floods the gutter.")
    assert (r.source, r.basis, r.tract_id) == ("intersection", "residence", tract_at(-121.87, 37.315))
    r, _ = resolve(refs, "I cross King and Story every night after work.", item_title="Story/King corridor lights")
    assert r.basis == "both"


def test_range_is_midpoint_of_two_crossings(refs):
    r, _ = resolve(refs, "The streetlights along King Road between Story and Tully have been out for a month.")
    # crossings at lat 37.305 and 37.335 -> midpoint 37.32 on King (lon -121.885), the TB/TD boundary
    assert (r.precision, r.source) == ("address", "intersection")
    assert r.point == pytest.approx((-121.885, 37.32))
    assert r.multi   # the King segment around the midpoint crosses a tract line


# --- single streets

def test_street_near_neighborhood_anchor(refs):
    r, g = resolve(refs, "I'm writing about the large pothole on Alma Avenue near Washington.")
    assert (r.precision, r.source, r.matched_name) == ("address", "street_anchor", "Washington-Guadalupe")
    assert r.point == pytest.approx((-121.875, 37.325))   # nearest point on Alma to the Washington centroid
    assert r.tract_id == TB or r.tract_id == TD


def test_fictional_place_resolves_through_real_street_and_area(refs):
    r, g = resolve(refs, "I live in Alviso and oppose the Terra Verde data center off Gold Street.")
    assert (r.precision, r.source, r.matched_name, r.basis) == ("address", "street_anchor", "Alviso", "both")
    assert r.point[0] == pytest.approx(-121.865) and not g.calls   # never geocoded by name


def test_cross_street_anchor(refs):
    r, _ = resolve(refs, "The pothole on Alma Ave is awful. Also Gold Street floods.")
    assert (r.source, r.tract_id) == ("street_anchor", tract_at(-121.865, 37.325))


def test_single_street_anchored_to_item_cluster_and_named_place_propagation(refs):
    rows = [row("I live near the crosswalk at Story and King.", "A"),
            row("Hey, I live near 5th and William and the lights are out.", "B"),
            row("Tenants at Cedar Court Apartments near Tully Road have had no hot water.", "C"),
            row("Cedar Court has had no hot water for nine days.", "D"),
            row("its freezing at our building off tully. been weeks.", "E")]
    res = rl.Resolver(refs, Geo(), GridStreets(), {})
    out = {r["comment_id"]: x for r, x in zip(rows, rl.resolve_all(res, rows))}
    assert out["C"].source == "street_anchor" and out["C"].point[1] == pytest.approx(37.335)   # on Tully
    assert out["D"].tract_id == out["C"].tract_id and out["D"].source == "street_anchor"      # not far-away Cedar Ct
    assert out["E"].point[1] == pytest.approx(37.335)
    assert res.stats["cluster_anchored"] >= 1 and res.stats["named_place_propagated"] == 1


def test_lone_street_without_any_anchor_stays_unlocated(refs):
    res = rl.Resolver(refs, Geo(), GridStreets(), {})
    out = rl.resolve_all(res, [row("The Alma Ave pothole must be fixed.")])
    assert out[0].precision == "none"


def test_spanish_and_freeway_forms(refs):
    r, _ = resolve(refs, "Vivo cerca de Story Road con mis tres hijos. Y la calle Alma tambien.")
    assert r.basis == "residence"
    ms = rl.find_streets("The air near my place by 101 is hazy.", GridStreets(), set())
    assert [m.base for m in ms] == ["101"]
    assert rl.find_streets("owners pull units off the market", GridStreets(), set()) == []


def test_street_multi_within_300m(refs):
    from shapely.geometry import LineString, Point
    res = rl.Resolver(refs, Geo(), GridStreets(), {})
    story = LineString(STREETS["story"][1])
    assert res.street_multi(story, Point(-121.881, 37.305))        # 90 m from the TA/TB line
    assert not res.street_multi(story, Point(-121.895, 37.305))    # ~1.3 km from any tract line


# --- neighborhood tier

def test_neighborhood_residence_and_issue(refs):
    r, _ = resolve(refs, "I have lived in downtown San Jose for 20 years.")
    assert (r.precision, r.tract_id, r.multi, r.basis) == ("neighborhood", TD, True, "residence")
    r, _ = resolve(refs, "Downtown San Jose needs more housing.")
    assert (r.precision, r.basis) == ("neighborhood", "issue")


def test_token_aware_fuzzy(refs):
    r, _ = resolve(refs, "As a homeowner in Wilow Glen, I am opposed.")
    assert (r.precision, r.matched_name) == ("neighborhood", "Willow Glen")
    r, _ = resolve(refs, "who is deserving of rights and who is not. San Jose should be a city")
    assert r.precision == "none"


def test_field_trusted_for_non_letter_channels_only(refs):
    r, _ = resolve(refs, "Fix the streets.", neighborhood="Willow Glen", channel="email")
    assert (r.precision, r.source, r.basis) == ("neighborhood", "field", "residence")
    r, _ = resolve(refs, "Fix the streets.", neighborhood="Willow Glen", channel="letter")
    assert r.precision == "none"


def test_item_title_place_now_resolves_as_issue(refs):
    title = "Streetlight reliability program (Story/King corridor)"
    r, _ = resolve(refs, "The lights at Story and King are out again.", item_title=title)
    assert (r.source, r.basis) == ("intersection", "issue")


def test_org_and_negated_mentions_rejected(refs):
    for t in ["Two lawsuits in Oregon and Washington D.C. argue otherwise.",
              "I serve as a trustee of the Willow Glen Union School District.",
              "I don't live in Willow Glen but I support this.",
              "He is a proud graduate of San Jose State University.",
              "Transit mega-projects (such as Diridon Station) need oversight."]:
        r, _ = resolve(refs, t, channel="letter")
        assert r.precision == "none", t


def test_generic_names_excluded(refs):
    names = {n for n, *_ in refs.nb_names}
    assert not names & {"commercial", "union", "estates"}
    r, _ = resolve(refs, "We met in a commercial zone near the Union hall in the Estates.")
    assert r.precision == "none"
    assert rl.eligible_name("Commercial", curated=True, words={"commercial"})


def test_landmark_with_proximity_cue(refs):
    r, _ = resolve(refs, "My neighbors near Kelley Park got a huge rent hike.")
    assert (r.precision, r.source, r.matched_name, r.basis) == ("address", "landmark", "Kelley Park", "residence")


# --- zip and district tiers

def test_zip_from_signature_uses_crosswalk(refs):
    r, _ = resolve(refs, "Please vote yes.\nSincerely\n[name removed]\nSan Jose, California 95125", channel="letter")
    assert (r.precision, r.source, r.tract_id, r.multi, r.basis) == ("zip", "signature", TA, True, "residence")
    r, _ = resolve(refs, "Please vote yes.\nSincerely\n[name removed]\nMorgan Hill, California 95037",
                   channel="letter")
    assert r.precision == "none"


def test_stated_district(refs):
    r, _ = resolve(refs, "I am a resident of District 5 and I support the memo.")
    assert (r.precision, r.tract_id, r.district, r.basis) == ("district", "", 5, "residence")
    r, _ = resolve(refs, "Please appoint her to the District 3 seat.")
    assert r.precision == "none" and r.district is None
    # with a tract, council_district describes the resolved place
    r, _ = resolve(refs, "I'm a District 5 resident. I have lived in Willow Glen for years.")
    assert r.tract_id == TA and r.district == 3


# --- privacy

def test_cache_keys_are_hashes_and_output_has_no_street_text(refs, tmp_path):
    c = rl.Cache(tmp_path / "cache.json")
    c.put("census|1234 lincoln ave, san jose, ca", TA, True, "census_onelineaddress")
    c.save()
    raw = (tmp_path / "cache.json").read_text()
    assert "lincoln" not in raw.lower() and re.search(r'"[0-9a-f]{64}"', raw)

    rows = [row(t, f"C{i}") for i, t in enumerate([
        "Sincerely,\nOrg\n55 Lincoln Ave\nSan Jose, CA 95125",
        "I live near the crosswalk at Story and King.",
        "Pothole on Alma Avenue near Washington.",
        "I have lived in Willow Glen for years."])]
    res = rl.Resolver(refs, Geo(), GridStreets(), {})
    out = pd.DataFrame([{"comment_id": r["comment_id"], "tract_id": x.tract_id, "precision": x.precision,
                         "source": x.source, "basis": x.basis, "matched_name": x.matched_name}
                        for r, x in zip(rows, rl.resolve_all(res, rows))])
    blob = out.to_csv(index=False)
    assert not rl.HOUSE_RE.search(blob)
    for s in ["Lincoln", "Story", "King", "Alma"]:
        assert s not in blob


def test_real_locations_csv_has_no_house_numbers_or_streets():
    p = rl.OUT_LOC
    if not p.exists():
        pytest.skip("run scripts/resolve_locations.py first")
    blob = p.read_text()
    assert not rl.HOUSE_RE.search(blob)
    df = pd.read_csv(p, dtype=str, keep_default_na=False)
    assert list(df.columns) == rl.OUT_COLS
    assert set(df.location_precision) <= set(rl.TIERS)
    assert set(df.location_basis) <= set(rl.BASES) | {""}
    assert (df.loc[df.location_precision.isin(["district", "none"]), "tract_id"] == "").all()
    assert (df.loc[df.location_precision != "none", "location_basis"] != "").all()
