import re
from pathlib import Path
from urllib.parse import urlparse
from config import *
from import_har import load as load_json
from capture_observed import load as load_observed
from capture_session import load as load_session
from media_mapping import load as load_media

LESSON_RX=re.compile(r"/DOS/(\d+)/(\d+)\.html$")
books_file=load_json(BOOKS_FILE,{})
um=load_json(URL_MAP_FILE,{})
obs=load_observed().get("requests",{})
visits=load_session().get("visits",[])
media=load_media().get("lessons",{})

books={}
for bid,b in books_file.items():
    books.setdefault(str(bid),set()).update(map(str,b.get("lessons",{}).keys()))
for u,rows in um.items():
    m=LESSON_RX.search(urlparse(u).path)
    if m and any(r.get("body_available") and r.get("status")==200 for r in rows):
        books.setdefault(m.group(1),set()).add(m.group(2))
for v in visits:
    if v.get("book") and v.get("lesson"):
        books.setdefault(str(v["book"]),set()).add(str(v["lesson"]))

def sts(r):
    z=set()
    for x in r.get("statuses",[]):
        try:z.add(int(x))
        except:pass
    return z
def important(u):
    return Path(urlparse(u).path).suffix.lower() in {
        ".html",".js",".css",".json",".svg",".png",".jpg",".jpeg",".webp",
        ".woff",".woff2",".ttf",".otf"}

for bid,lids in sorted(books.items()):
    starts={str(v["lesson"]) for v in visits if str(v.get("book"))==bid and v.get("kind")=="lesson-start" and v.get("lesson")}
    dones={str(v["lesson"]) for v in visits if str(v.get("book"))==bid and v.get("kind")=="lesson-done" and v.get("lesson")}
    only304=[]; upstream404=[]; gaps=[]
    for u,r in obs.items():
        refs=" ".join(r.get("referers",[]))
        if f"/DOS/{bid}/" not in urlparse(u).path and f"/publication/{bid}/" not in urlparse(u).path and f"/DOS/{bid}/" not in refs:continue
        st=sts(r)
        if 304 in st and not ({200,206}&st):only304.append(u)
        if important(u) and st=={404}:upstream404.append(u)

    mapped=set()
    for lid in lids:
        for x in media.get(f"{bid}/{lid}",{}).get("media",[]):
            if isinstance(x,dict) and x.get("strict") and x.get("url"):mapped.add(x["url"])
    incomplete=[]
    for u in mapped:
        rows=um.get(u,[])
        if not any(r.get("complete") or r.get("source")=="assembled_ranges" for r in rows):incomplete.append(u)

    traversal_ok = bool(lids) and (len(dones)>=len(lids) or (starts and starts<=dones))
    failures=[]
    if not traversal_ok:failures.append(f"lesson traversal incomplete ({len(dones)}/{len(lids)})")
    if only304:failures.append(f"{len(only304)} resource(s) remain 304-only")
    if incomplete:failures.append(f"{len(incomplete)} mapped MP4 incomplete")
    label="INCOMPLETE" if failures else ("READY WITH WARNINGS" if upstream404 else "READY")
    print(f"[{label}] BOOK {bid}")
    print("Lessons known:",len(lids))
    print("Traversal starts:",len(starts))
    print("Traversal done:",len(dones),"/",len(lids))
    print("304-only resources:",len(only304))
    print("Mapped media URLs:",len(mapped))
    print("Mapped MP4 incomplete:",len(incomplete))
    print("Upstream 404 warnings:",len(upstream404))
    for u in upstream404[:30]:print("  UPSTREAM 404",u)
    for f in failures:print("  FAILURE",f)
    print()
