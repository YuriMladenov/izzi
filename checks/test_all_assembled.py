import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import urllib.request,urllib.error
from assembled_media import build_index
from urllib.parse import urlparse
from config import CLIENT_HOST,PORT
exact,_=build_index()
print("IZZI v3.2.3 assembled MP4 HTTP tests")
if not exact: print("No complete MP4s indexed.")
fail=0
for u in exact:
    p=urlparse(u)
    local=f"http://{CLIENT_HOST}:{PORT}{p.path}"+(("?"+p.query) if p.query else "")
    req=urllib.request.Request(local,headers={"Range":"bytes=0-1023"})
    try:
        with urllib.request.urlopen(req) as r:
            b=r.read()
            ok=r.status==206 and (r.headers.get("Content-Type") or "").startswith("video/mp4") and len(b)==1024
            print("PASS" if ok else "FAIL",r.status,r.headers.get("Content-Range"),local)
            fail+=not ok
    except Exception as e: print("FAIL",local,e);fail+=1

raise SystemExit(bool(fail))
