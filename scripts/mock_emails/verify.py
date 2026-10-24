import json, sys, pandas as pd
from pathlib import Path
from collections import Counter
SCR = sys.argv[1]
side = json.load(open(f"{SCR}/side.json"))
e = pd.read_csv(str(Path(__file__).resolve().parents[2]) + "/data/emails_raw.csv", dtype=str, keep_default_na=False)
e = e[e.generated == "True"]
loc = pd.read_csv(str(Path(__file__).resolve().parents[2]) + "/data/locations.csv", dtype=str, keep_default_na=False).set_index("comment_id")
bad, ovr = [], {}
try: ovr = json.load(open(f"{SCR}/overrides.json"))
except Exception: pass
stats = Counter()
for r in e.itertuples():
    s = side[int(r.source_row)]
    l = loc.loc[r.comment_id]
    m = s.get("method")
    want = s.get("tract")
    if m in ("int", "nb"):
        ok = l.tract_id == want and l.location_basis in ("residence", "both")
        stats[(m, ok)] += 1
        if not ok:
            bad.append((s["key"], m, s.get("pair") or s.get("nb"), want, l.tract_id, l.location_precision, l.location_source, l.location_basis))
            if m == "int" and s["key"][0:5] == "06085":
                o = ovr.setdefault(s["key"], {}); o.setdefault("skip_int", []).append(s["pair"])
                if len(o["skip_int"]) >= 3: o["force"] = "nb"
    else:
        stats[(m, l.location_precision)] += 1
        if m == "none" and l.location_precision not in ("none",):
            bad.append((s["key"], m, r.text[:120].replace("\n", " "), "", l.tract_id, l.location_precision, l.location_source, l.location_basis))
for b in bad: print(b)
print(stats)
json.dump(ovr, open(f"{SCR}/overrides.json", "w"), indent=1)
