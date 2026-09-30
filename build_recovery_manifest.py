import json
from config import STATE_DIR
from capture_observed import load as load_observed
from cache_bust_recovery import eligible
OUT=STATE_DIR/"recovery_manifest.json"
urls=[]
for u,r in load_observed().get("requests",{}).items():
    sts={int(x) for x in r.get("statuses",[]) if str(x).isdigit()}
    if 304 in sts and not ({200,206}&sts) and eligible(u): urls.append(u)
urls=sorted(set(urls))
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps({"urls":urls},ensure_ascii=False,indent=2),encoding="utf-8")
print("Recovery manifest:",len(urls),"eligible 304-only URLs")
