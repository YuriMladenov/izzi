import gzip,json,zlib
from pathlib import Path
from urllib.parse import urlparse
from config import *
from import_har import load
m=load(URL_MAP_FILE,{})
bad=[];ok=0
for u,rs in m.items():
    ext=Path(urlparse(u).path).suffix.lower()
    if ext not in {".js",".css",".html",".json",".svg"}:continue
    for r in reversed(rs):
        if not r.get("body_available") or not r.get("key"):continue
        f=ARCHIVE_DIR/r["key"]
        if not f.exists():continue
        b=f.read_bytes()[:8]
        suspicious=b.startswith(b"\\x1f\\x8b") or (len(b)>=2 and b[0]==0x78 and b[1] in (0x01,0x5e,0x9c,0xda))
        if suspicious:bad.append((u,r["key"],b.hex()))
        else:ok+=1
        break
print("Text resources checked:",ok+len(bad))
print("Looks decoded:",ok)
print("Looks compressed/corrupt:",len(bad))
for x in bad[:100]:print("[BAD]",*x)
print("\\nRecapture BAD resources with v3.2 + Firefox DevTools > Network > Disable Cache.")
