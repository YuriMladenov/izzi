import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cache_bust_recovery import load
a=load().get("attempts",{}); ok=[]; bad=[]
for u,rows in a.items():
    (ok if any(x.get("status")==200 and x.get("size",0)>0 for x in rows) else bad).append(u)
print("IZZI v3.3.3 Cache-Bust Recovery Report")
print("Recovered with body:",len(ok))
print("Not recovered:",len(bad))
for u in bad[:100]: print("  FAIL",u)
