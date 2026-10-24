import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import bob_label as B
SCR = sys.argv[1]
side = json.load(open(f"{SCR}/side.json"))
cats = json.loads(B.CATS.read_text())
e = pd.read_csv(str(Path(__file__).resolve().parents[2]) + "/data/emails_raw.csv", dtype=str, keep_default_na=False)
e = e[e.generated == "True"]
agent, act, errs = {}, {}, 0
for r in e.itertuples():
    s = side[int(r.source_row)]
    lab, er = B.validate(dict(s["label"]), cats, r.text[:B.TEXT_CAP])
    if er:
        errs += 1; print(r.comment_id, s["key"], er); continue
    lab["subcategory"] = s["label"]["subcategory"]
    lab["bob_task_id"] = ""
    agent[r.comment_id] = lab
    act[r.comment_id] = s["actionable"]
(B.WORK / "agent_labels.json").write_text(json.dumps(agent, ensure_ascii=False, indent=1))
(B.WORK / "actionable_agent.json").write_text(json.dumps(act, ensure_ascii=False, indent=1))
print(len(agent), "labels;", len(act), "actionable;", errs, "errors")
