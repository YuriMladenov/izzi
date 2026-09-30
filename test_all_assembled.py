import urllib.request,urllib.error
from assembled_media import build_index
from urllib.parse import urlparse
from config import HOST,PORT
exact,_=build_index()
print("IZZI v3.2.3 assembled MP4 HTTP tests")
if not exact: print("No complete MP4s indexed.")
for u in exact:
    p=urlparse(u)
    local=f"http://{HOST}:{PORT}{p.path}"+(("?"+p.query) if p.query else "")
    req=urllib.request.Request(local,headers={"Range":"bytes=0-1023"})
    try:
        with urllib.request.urlopen(req) as r:
            b=r.read()
            ok=r.status==206 and (r.headers.get("Content-Type") or "").startswith("video/mp4") and len(b)==1024
            print("PASS" if ok else "FAIL",r.status,r.headers.get("Content-Range"),local)
    except Exception as e: print("FAIL",local,e)
