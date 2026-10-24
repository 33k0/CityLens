import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fairness as fz  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "public" / "data" / "fairness"


@pytest.fixture(scope="module")
def city():
    tracts, comments, totals, by_cat = fz.synthetic()
    return fz.build_city(tracts, comments, totals, by_cat, 12)


def _pandas(units, attr, weighted):
    w = units["population"].astype(float) if weighted else pd.Series(1.0, index=units.index)
    br = {}
    for g in (0, 1):
        m = units[attr] == g
        br[g] = (w[m] * units.loc[m, "favorable"]).sum() / w[m].sum()
    return br[0] / br[1] if br[1] else None, br[0] - br[1]


@pytest.mark.parametrize("family", ["voice", "problems"])
@pytest.mark.parametrize("attr", list(fz.ATTRIBUTES))
@pytest.mark.parametrize("weighted", [False, True])
def test_aif360_matches_pandas(city, family, attr, weighted):
    units = city.units(family)
    m = fz.measure(units, attr, weighted)
    di, spd = _pandas(units, attr, weighted)
    assert abs(m["spd"] - spd) <= 1e-9
    assert (m["di"] is None and di is None) or abs(m["di"] - di) <= 1e-9


def test_weighted_differs_from_unweighted(city):
    # AIF360 honours instance_weights: the population-weighted result is not the unweighted one
    u = city.units("problems")
    assert fz.measure(u, "majority_nonwhite", True)["spd"] != fz.measure(u, "majority_nonwhite", False)["spd"]


def test_reweighing_cells(city):
    u = city.units("voice")
    cells, tw = fz.reweighing_weights(u, "low_income")
    # Reweighing equalises the weighted base rates across groups
    w = tw.values
    rates = [(w[(u["low_income"] == g).values] * u["favorable"].values[(u["low_income"] == g).values]).sum()
             / w[(u["low_income"] == g).values].sum() for g in (0, 1)]
    assert abs(rates[0] - rates[1]) <= 1e-9


def test_city_median_computed_once(city):
    before = dict(city.medians)
    n = city.median_computations
    ids = list(city.tracts.index)
    fz.region_summary(ids[:20], city)
    fz.region_summary(ids[20:], city, "high_lep")
    assert dict(city.medians) == before and city.median_computations == n
    with pytest.raises(TypeError):
        city.medians["voice"] = 0  # read-only mapping


def test_region_uses_citywide_median(city):
    # pick tracts all below the citywide 311 median: with a region median they would split; citywide they are all 0
    below = [t for t in city.tracts.index if city.rates["problems"][t] <= city.medians["problems"]]
    r = fz.region_summary(below, city)
    if not r["not_enough_data"]:
        m = r["requests_311"]["unweighted"]
        assert m["privileged"]["favorable"] == 0 and m["unprivileged"]["favorable"] == 0


def test_not_enough_data(city):
    ids = list(city.tracts.index)
    r = fz.region_summary(ids[:4], city)
    assert r["not_enough_data"] and "fewer than 5 tracts" in r["reasons"]
    assert r["counts"]["n_tracts"] == 4 and "voice" in r["counts"] and "requests_311" in r["counts"]
    priv = [t for t in ids if city.tracts.at[t, "low_income"] == 1]
    unpriv = [t for t in ids if city.tracts.at[t, "low_income"] == 0]
    r = fz.region_summary(priv[:6] + unpriv[:1], city)
    assert r["not_enough_data"] and any("group" in x for x in r["reasons"])
    quiet = [t for t in ids if city.voice_by_tract[t] < 1][:8]
    r = fz.region_summary(quiet, city)
    assert r["not_enough_data"] and any("voice" in x for x in r["reasons"])
    assert not fz.region_summary(ids, city)["not_enough_data"]


def test_families_never_blended(city):
    r = fz.region_summary(list(city.tracts.index), city)
    assert set(["voice", "requests_311"]) <= set(r) and r["voice"]["family"] == "voice" and r["requests_311"]["family"] == "problems"
    assert r["counts"]["voice"]["count"] != r["counts"]["voice"]["count"] + r["counts"]["requests_311"]["count"]
    mixed = city.comments + [{"comment_id": "x", "tract_id": "s000", "channel": "311", "item": "S-1", "category": "theme_b"}]
    with pytest.raises(ValueError):
        fz.region_summary(list(city.tracts.index), city, voice_comments=mixed)
    with pytest.raises(ValueError):
        fz.region_summary(list(city.tracts.index), city, problem_rows=[{"channel": "letter", "n": 3, "tract_id": "s000"}])
    with pytest.raises(ValueError):
        fz.build_city(*fz.synthetic()[:1], mixed, *fz.synthetic()[2:], 12)


def test_voice_counting_rules():
    rows = [{"channel": "letter", "campaign_id": "C", "duplicate_of": None}] * 3 + [
        {"channel": "letter", "campaign_id": "C", "duplicate_of": "x"}, {"channel": "email", "campaign_id": None, "duplicate_of": None}]
    w = fz.voice_row_weights(rows)
    assert abs(sum(w) - 2) < 1e-12 and w[3] == 0
    assert sum(fz.voice_row_weights(rows, "raw")) == 5


def test_unlocated_reported_not_mapped(city):
    vc = fz.voice_counts(city.comments, city.tracts.index)
    assert vc["unlocated"] >= 1 and abs(vc["total"] - vc["located"] - vc["unlocated"]) < 1e-9
    assert abs(vc["by_tract"].sum() - vc["located"]) < 1e-9


def test_labels_illustrative_when_mock(city):
    lab = fz.labels(city, "voice")
    assert lab["real"] is False and lab["label"] == "illustrative"
    assert fz.labels(city, "problems")["real"] is True


def test_demo_audit_and_brief_wording(city):
    a = fz.audit(city, "voice")
    texts = [b["text"] for b in a["briefs"]] + [b["text"] for it in a["per_item"].values() for b in it.get("briefs", [])]
    assert texts
    for t in texts:
        for w in fz.BANNED_WORDS:
            assert w not in t.lower()


@pytest.mark.skipif(not (OUT / "voice_city.json").exists(), reason="run scripts/fairness.py first")
def test_exported_files():
    meta = json.loads((OUT / "meta.json").read_text())
    assert set(meta["attributes"]) == set(fz.ATTRIBUTES) and meta["aif360_version"]
    prob = json.loads((OUT / "311_city.json").read_text())
    assert prob["family"] == "problems" and prob["real"] is True
    voice = json.loads((OUT / "voice_city.json").read_text())
    assert voice["family"] == "voice"
    if any(c > 0 for c in [voice.get("channels", {}).get("email", {}).get("rows", 0)]):
        assert voice["real"] is False and voice["label"] == "illustrative"
    blob = json.dumps(voice.get("briefs", [])) + json.dumps(voice.get("per_item", {}))
    for w in fz.BANNED_WORDS:
        assert w not in blob.lower()
    pwv = json.loads((OUT / "problems_without_voice.json").read_text())
    for r in pwv["rows"]:
        assert "problem_pct" in r and "voice_pct" in r and r["problem_pct"] >= 70 and r["voice_pct"] <= 30
    assert prob["city_median_rate_per_1k"] == meta["city_median_rate_per_1k"]["problems"]


def test_location_basis_rule():
    mk = lambda i, b: {"comment_id": f"c{i}", "tract_id": "t1", "channel": "letter", "location_basis": b}
    rows = [mk(i, "residence") for i in range(20)] + [mk(100 + i, "both") for i in range(10)] + [mk(200 + i, "issue") for i in range(15)]
    basis, part, counts = fz.participation_basis(rows)
    assert basis == "residence" and counts["residence_rows"] == 30
    assert sum(1 for c in part if c["tract_id"]) == 30 and len(part) == len(rows)  # issue rows kept, but not mapped
    basis, part, _ = fz.participation_basis(rows[1:])
    assert basis == "all_located" and sum(1 for c in part if c["tract_id"]) == 44
    tagged = fz.attach_location_basis([{"comment_id": "a", "tract_id": "t1"}, {"comment_id": "b", "tract_id": None}])
    assert tagged[0]["location_basis"] == "unknown" and tagged[1]["location_basis"] is None
