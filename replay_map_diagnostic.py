import json,re
from pathlib import Path
from urllib.parse import urlparse,unquote
from config import *
from import_har import load as load_json

m=load_json(URL_MAP_FILE,{})
def canon(path):
    path=unquote(path)
    x=re.match(r"^/DOS/(\d+)/(.*)$",path)
    if x:
        tail="/"+x.group(2)
        if tail.startswith(("/datastore/","/profil/","/_nuxt/")):return tail
    return path

lesson=[]; fonts=[]; mp4=[]
for u,rs in m.items():
    p=urlparse(u); path=unquote(p.path)
    usable=[r for r in rs if isinstance(r,dict) and r.get("body_available") and r.get("key")]
    if not usable:continue
    if re.search(r"/DOS/\d+/\d+\.html$",path):lesson.append((u,len(usable)))
    ext=Path(path).suffix.lower()
    if ext in {".woff",".woff2",".ttf",".otf"}:fonts.append((u,len(usable)))
    if ext==".mp4":mp4.append((u,len(usable)))
print("IZZI v3.4.2 Replay Map Diagnostic")
print("URL map entries:",len(m))
print("Usable lesson HTML URLs:",len(lesson))
print("Usable font URLs:",len(fonts))
print("Usable MP4 URL records:",len(mp4))
for label,arr in (("LESSON",lesson[:5]),("FONT",fonts[:5]),("MP4",mp4[:5])):
    for u,n in arr:print(label,n,u)
target="/DOS/1408736/1408788.html"
matches=[u for u in m if canon(urlparse(u).path)==canon(target)]
print("Canonical matches for",target,":",len(matches))
for u in matches[:10]:print("  MATCH",u)
