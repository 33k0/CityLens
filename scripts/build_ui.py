#!/usr/bin/env python3
"""Step j: package the tract layer for the map UI -> public/data/ui.json.

One record per San José census tract with its geometry, ACS 2024 profile, council district and a display
neighborhood name, plus the city outline and the attribute thresholds the fairness step uses. Comments, 311 and
fairness numbers are NOT copied here; the UI reads them from their own files so there is one source of truth.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "public" / "data"
OUT = PUB / "ui.json"


def polys_only(geom):
    """Clipping can leave GeometryCollections with stray lines/points; keep only the polygon parts."""
    from shapely.geometry import MultiPolygon, Polygon
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    parts = []
    for g in getattr(geom, "geoms", []):
        if isinstance(g, Polygon):
            parts.append(g)
        elif isinstance(g, MultiPolygon):
            parts.extend(g.geoms)
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


def rnd(geom, nd=5):
    geom = polys_only(geom)

    def r(c):
        return [round(c[0], nd), round(c[1], nd)] if isinstance(c[0], float) else [r(x) for x in c]
    m = mapping(geom)
    return {"type": m["type"], "coordinates": r(m["coordinates"])}


def main() -> int:
    tg = gpd.read_file(PUB / "tracts.geojson")
    acs = pd.read_csv(ROOT / "data" / "tracts.csv", dtype={"tract_id": str}).set_index("tract_id")
    nb = pd.read_csv(ROOT / "data" / "neighborhoods.csv", dtype=str).fillna("")
    dist = gpd.read_file(PUB / "council_districts.geojson")
    meta = json.loads((PUB / "fairness" / "meta.json").read_text())
    # household language (ACS C16002, cached by build_tracts.py): households by language spoken at home
    lang = pd.read_csv(ROOT / "data" / "raw" / "census" / "acs5_2024_c16002_06085.psv", sep="|", dtype=str)
    lang["tract_id"] = lang["GEO_ID"].str[-11:]
    lang = lang.set_index("tract_id")
    LCOL = {"english_only": "C16002_E002", "spanish": "C16002_E003", "other_indo_european": "C16002_E006",
            "asian_pacific": "C16002_E009", "other": "C16002_E012"}
    # MTC Equity Priority Communities 2024 (ACS 2018-2022, 2020 tracts), via the city's mirror of the MTC layer
    epc_raw = json.loads((ROOT / "data" / "raw" / "census" / "sjgis_equity_priority_communities.json").read_text())
    epc = {str(f["attributes"]["GEOID"]).zfill(11): f["attributes"]["EQUITYPRIORITYCOMMUNITYCLASS"] for f in epc_raw["features"]}

    # display name: a neighborhood whose containing tract (first in its list) is this tract; curated names first
    curated = nb[(nb["source"] == "hand") | (nb["aliases"] != "")]
    first = {}
    for frame in (curated, nb):
        for r in frame.itertuples():
            ids = [x for x in r.tract_ids.split("|") if x]
            if ids and ids[0] not in first:
                first[ids[0]] = r.name
    nbp = gpd.GeoDataFrame(nb, geometry=gpd.points_from_xy(nb["lon"].astype(float), nb["lat"].astype(float)), crs=4326).to_crs(3310)

    cent = tg.to_crs(3310).centroid
    cent_ll = gpd.GeoSeries(cent, crs=3310).to_crs(4326)
    dj = gpd.sjoin(gpd.GeoDataFrame(tg[["tract_id"]], geometry=cent_ll.values, crs=4326), dist[["district", "geometry"]], predicate="within")
    dmap = dict(zip(dj["tract_id"], dj["district"]))

    tracts = []
    for i, row in tg.iterrows():
        t = row["tract_id"]
        name = first.get(t)
        if not name:  # nearest named neighborhood centroid within 2 km
            d = nbp.distance(cent.iloc[i])
            j = d.idxmin()
            name = nb.loc[j, "name"] if d[j] <= 2000 else "San José"
        a = acs.loc[t]
        c = cent_ll.iloc[i]
        tracts.append({
            "id": t, "label": row["name"].replace("Census Tract ", ""), "nbhd": name,
            "c": [round(c.x, 5), round(c.y, 5)], "pop": int(a["population"]),
            "renter": round(float(a["pct_renter"]), 4), "lep": round(float(a["pct_lep"]), 4),
            "income": int(a["median_income"]), "nonwhite": round(float(a["pct_nonwhite"]), 4),
            "district": int(dmap[t]) if t in dmap else None,
            "households": int(lang.loc[t, "C16002_E001"]) if t in lang.index else None,
            "lang": ({k: round(int(lang.loc[t, v]) / max(1, int(lang.loc[t, "C16002_E001"])), 4) for k, v in LCOL.items()}
                     if t in lang.index else None),
            "epc": epc.get(t),  # High | Higher | Highest = Equity Priority Community; NA = not; None = not in MTC data
            "geometry": rnd(row.geometry)})
    city = tg.to_crs(3310).buffer(1).union_all().buffer(-1)
    city = gpd.GeoSeries([city], crs=3310).to_crs(4326).iloc[0].simplify(0.0002)
    th = {k: v.get("threshold") for k, v in meta["attributes"].items()}
    OUT.write_text(json.dumps({"source": "TIGER 2024 tracts clipped to San José city limits; ACS 5-year 2020–2024; "
                               "household language ACS C16002; MTC Equity Priority Communities 2024 (ACS 2018–2022)",
                               "acs_years": "2020–2024", "thresholds": th, "attributes": meta["attributes"],
                               "city": rnd(city), "tracts": tracts}, separators=(",", ":"), allow_nan=False))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(tracts)} tracts, {OUT.stat().st_size // 1024} KB; "
          f"named {sum(1 for t in tracts if t['nbhd'] != 'San José')}; thresholds {th}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
