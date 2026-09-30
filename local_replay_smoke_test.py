import urllib.request,urllib.error,json
from pathlib import Path
from urllib.parse import urlparse
from config import *
from import_har import load as load_json
base=f"http://{HOST}:{PORT}"
books=load_json(BOOKS_FILE,{})
um=load_json(URL_MAP_FILE,{})
tests=[("/",None)]
for bid,b in books.items():
    for lid in b.get("lessons",{}): tests.append((f"/DOS/{bid}/{lid}.html","text/html"))
for u,rows in um.items():
    ext=Path(urlparse(u).path).suffix.lower()
    if ext in {".woff2",".woff"}:
        p=urlparse(u); tests.append((p.path+("?"+p.query if p.query else ""),"font/"))
    if ext==".mp4" and any(r.get("complete") or r.get("source")=="assembled_ranges" for r in rows):
        p=urlparse(u); tests.append((p.path+("?"+p.query if p.query else ""),"video/mp4"))
ok=fail=0
seen=set()
for path,ctype in tests:
    if path in seen:continue
    seen.add(path)
    req=urllib.request.Request(base+path,headers={"Range":"bytes=0-1023"} if ctype=="video/mp4" else {})
    try:
        with urllib.request.urlopen(req,timeout=10) as r:
            got=r.headers.get("Content-Type","")
            good=r.status in (200,206) and (not ctype or got.startswith(ctype))
            print("PASS" if good else "FAIL",r.status,got,path)
            ok+=bool(good);fail+=not good
    except Exception as e:
        print("FAIL",path,e);fail+=1
print("Smoke test:",ok,"passed,",fail,"failed")
