from pathlib import Path
from urllib.parse import urlparse
from capture_observed import load
from config import ARCHIVE_DIR,URL_MAP_FILE
from import_har import load as jload
M=jload(URL_MAP_FILE,{})
O=load().get("requests",{})
EXT={".woff",".woff2",".ttf",".otf",".js",".css",".json",".svg",".png",".jpg",".jpeg",".webp",".gif"}
def ok(u):
    p=urlparse(u)
    for uu,rs in M.items():
        pp=urlparse(uu)
        if (uu==u or (pp.netloc.lower()==p.netloc.lower() and pp.path==p.path)):
            for r in rs:
                if r.get("body_available") and r.get("key") and (ARCHIVE_DIR/r["key"]).exists() and r.get("status") in (200,206):
                    return True
    return False
print("IZZI v3.3.1 Missing Important Assets")
n=0
for u,r in sorted(O.items()):
    ext=Path(urlparse(u).path).suffix.lower()
    if (ext in EXT or urlparse(u).path.endswith("/search-index.js")) and not ok(u):
        n+=1; print("MISSING",u,"observed_statuses=",r.get("statuses"))
print("Total:",n)
