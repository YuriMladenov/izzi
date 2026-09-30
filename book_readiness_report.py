import re,json
from pathlib import Path
from urllib.parse import urlparse
from config import *
from import_har import load
from media_mapping import load as load_media
from assembled_media import build_index
from capture_session import load as load_session
from capture_observed import load as load_observed

LESSON_RX=re.compile(r"/DOS/(\d+)/(\d+)\.html")
FONT_EXT={".woff",".woff2",".ttf",".otf"}
STATIC_EXT={".js",".css",".json",".svg",".png",".jpg",".jpeg",".webp",".gif"}
m=load(URL_MAP_FILE,{})
media=load_media().get("lessons",{})
obs=load_observed().get("requests",{})
exact,paths=build_index()
sess=load_session()

def available_url(u):
    rs=m.get(u,[])
    if any(r.get("body_available") and r.get("key") and (ARCHIVE_DIR/r["key"]).exists()
           and r.get("status") in (200,206) for r in rs): return True
    p=urlparse(u)
    for uu,rr in m.items():
        pp=urlparse(uu)
        if pp.netloc.lower()==p.netloc.lower() and pp.path==p.path:
            if any(r.get("body_available") and r.get("key") and (ARCHIVE_DIR/r["key"]).exists()
                   and r.get("status") in (200,206) for r in rr): return True
    return False

books={}
for u,rs in m.items():
    mm=LESSON_RX.search(urlparse(u).path)
    if mm and any(r.get("body_available") and r.get("status")==200 for r in rs):
        books.setdefault(mm.group(1),set()).add(mm.group(2))
for v in sess.get("visits",[]):
    if v.get("book") and v.get("lesson"):
        books.setdefault(v["book"],set()).add(v["lesson"])

print("IZZI v3.3.1 Capture Completeness Report")
print("="*40)
all_missing=[]
for book,lids in sorted(books.items()):
    mapped_urls=set()
    mapped_lessons=0
    for lid in lids:
        e=media.get(f"{book}/{lid}",{})
        urls=[i.get("url") for i in e.get("media",[]) if i.get("url") and i.get("strict")]
        if urls: mapped_lessons+=1
        mapped_urls.update(urls)
    complete_mp4=[]
    incomplete_mp4=[]
    for u in mapped_urls:
        p=urlparse(u)
        if u in exact or (p.netloc.lower(),p.path) in paths: complete_mp4.append(u)
        else: incomplete_mp4.append(u)

    relevant=[]
    for u,r in obs.items():
        refs=" ".join(r.get("referers",[]))
        if f"/DOS/{book}/" in urlparse(u).path or f"/DOS/{book}/" in refs:
            relevant.append((u,r))
    missing=[]
    for u,r in relevant:
        ext=Path(urlparse(u).path).suffix.lower()
        important=ext in FONT_EXT or ext in STATIC_EXT or urlparse(u).path.endswith("/search-index.js")
        if important and not available_url(u):
            missing.append((u,r))
    all_missing.extend(missing)

    starts={(v.get("book"),v.get("lesson")) for v in sess.get("visits",[]) if v.get("kind")=="lesson-start" and v.get("book")==book}
    dones={(v.get("book"),v.get("lesson")) for v in sess.get("visits",[]) if v.get("kind")=="lesson-done" and v.get("book")==book}
    unfinished=starts-dones

    if incomplete_mp4 or missing or unfinished: state="INCOMPLETE"
    else: state="READY"
    print(f"\n[{state}] BOOK {book}")
    print("Lessons known:",len(lids))
    print("Traversal done:",len(dones),"/",len(starts) if starts else len(lids))
    print("Lessons with strict media mapping:",mapped_lessons)
    print("Mapped MP4 complete:",len(complete_mp4),"/",len(mapped_urls))
    print("Missing important static/font assets:",len(missing))
    for u,r in missing[:40]:
        print("  MISSING",Path(urlparse(u).path).suffix.lower() or "-",u,"statuses=",r.get("statuses"))
    for u in incomplete_mp4:
        print("  INCOMPLETE MP4",u)
    for x in sorted(unfinished):
        print("  UNFINISHED LESSON",x[1])

print("\nLegend: READY = no known incomplete traversal, mapped MP4, or observed important static/font gaps.")
print("Resources loaded only after manual interaction cannot be declared complete until that interaction is captured.")
