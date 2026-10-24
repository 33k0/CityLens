import json, sys, pandas as pd, numpy as np
from pathlib import Path
from collections import Counter
from scipy.stats import spearmanr
R = str(Path(__file__).resolve().parents[2]) + "/"
ui = pd.DataFrame(json.load(open(R + "public/data/ui.json"))["tracts"]).set_index("id")
C = json.load(open(R + "public/data/comments.json"))["comments"]
cm = pd.DataFrame(C)
if "generated" not in cm: cm["generated"] = False
cm["generated"] = cm.generated.fillna(False).astype(bool)
print("comments", len(cm), "emails", (cm.channel == "email").sum(), "generated", cm.generated.sum())
loc = cm[cm.tract_id.notna()]
print("tracts with >=1 located comment (any basis):", loc.tract_id.nunique())
res = loc[loc.location_basis.isin(["residence", "both"])]
print("tracts with >=1 residence comment:", res.tract_id.nunique())
print("by district (tracts covered / total):")
for d, g in ui.groupby("district", dropna=False):
    print("  D", d, loc.tract_id[loc.tract_id.isin(g.index)].nunique(), "/", len(g))
g = cm[cm.generated]
print("precision (generated):", g.location_precision.value_counts().to_dict())
print("precision (all emails):", cm[cm.channel == "email"].location_precision.value_counts().to_dict())
print("language (generated):", g.language.value_counts().to_dict())
print("engine all:", cm.engine.value_counts().to_dict(), "| existing rows:", cm[~cm.generated].engine.value_counts().to_dict())
# rates (UI style: all located, raw counts) and fairness style (residence basis; from voice_city.json if available)
for name, df in [("UI all-located raw", loc), ("residence basis", res)]:
    n = df.groupby("tract_id").size().reindex(ui.index).fillna(0)
    rate = n / ui["pop"] * 1000
    epc = ui.epc.isin(["High", "Higher", "Highest"]).astype(int)
    print(f"[{name}] median rate/1k={rate.median():.3f}  zero tracts={(n == 0).sum()}")
    for col, s in [("income", ui.income), ("renter", ui.renter), ("lep", ui.lep), ("epc", epc)]:
        ok = s.notna()
        rho, p = spearmanr(rate[ok], s[ok])
        print(f"   spearman(rate,{col}) = {rho:+.3f} (p={p:.3g})")
vc = json.load(open(R + "public/data/fairness/voice_city.json"))
def walk(o, path=""):
    if isinstance(o, dict):
        if "di" in o or "disparate_impact" in o:
            print("  ", path, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in o.items() if k in ("di", "spd", "disparate_impact", "statistical_parity_difference", "p_unpriv", "p_priv")})
        for k, v in o.items():
            if isinstance(v, (dict, list)) and k not in ("tracts",):
                walk(v, path + "." + k)
walk(vc.get("measure", vc), "measure")
print("city median voice rate (fairness.py):", vc.get("city_median_rate_per_1k") or vc.get("median"))
pw = json.load(open(R + "public/data/fairness/problems_without_voice.json"))["rows"]
print("problems without voice: n =", len(pw))
for i, r in enumerate(pw[:15]):
    t = ui.loc[r["tract_id"]]
    print(f"  {i+1:2d} {r['tract_id']} {t.nbhd:28s} D{t.district} 311pct={r['problem_pct']:.0f} voicepct={r['voice_pct']:.0f} renter={t.renter:.2f} lep={t.lep:.2f} inc={t.income} epc={t.epc}")
n = loc.groupby("tract_id").size().reindex(ui.index).fillna(0)
exp = ui["pop"] / ui["pop"].sum() * len(loc)
u = pd.DataFrame({"n": n, "exp": exp, "nb": ui.nbhd, "d": ui.district, "renter": ui.renter, "lep": ui.lep, "inc": ui.income, "epc": ui.epc})
u["miss"] = u.exp - u.n
print("under-represented (n/exp<0.5):", int((u.n / u.exp < 0.5).sum()))
for i, (t, r) in enumerate(u.sort_values("miss", ascending=False).head(15).iterrows()):
    print(f"  {i+1:2d} {t} {r.nb:28s} D{r.d} n={int(r.n)} exp={r.exp:.1f} renter={r.renter:.2f} lep={r.lep:.2f} inc={r.inc} epc={r.epc}")
