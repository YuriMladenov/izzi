import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capture_observed import load
O=load().get("requests",{})
counts={}
bad=[]
for u,r in O.items():
    for st in r.get("statuses",[]):
        counts[st]=counts.get(st,0)+1
    if 304 in r.get("statuses",[]) and not any(x in r.get("statuses",[]) for x in (200,206)):
        bad.append(u)
print("IZZI v3.3.2 Forced Fresh Capture Report")
print("Observed URLs:",len(O))
print("Status counts by URL-presence:",dict(sorted(counts.items())))
print("304-only URLs:",len(bad))
for u in bad[:100]:
    print("  304-ONLY",u)
if not bad:
    print("OK: no observed resource remains 304-only.")
