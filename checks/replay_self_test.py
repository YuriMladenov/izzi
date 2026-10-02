import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hashlib,json
from pathlib import Path
from urllib.parse import urlparse
from config import *
from import_har import load as load_json

um=load_json(URL_MAP_FILE,{})
checked=bad=fonts=fontbad=media=mediabad=0
missing=[]
for u,rows in um.items():
    for r in rows:
        if not r.get("body_available"): continue
        key=r.get("key")
        if not key: continue
        p=ARCHIVE_DIR/key
        checked+=1
        if not p.exists():
            bad+=1;missing.append((u,key));continue
        ext=Path(urlparse(u).path).suffix.lower()
        if ext in {".woff",".woff2",".ttf",".otf"}:
            fonts+=1
            if p.stat().st_size<100: fontbad+=1
        if ext==".mp4" and (r.get("complete") or r.get("source")=="assembled_ranges"):
            media+=1
            if p.stat().st_size<1024: mediabad+=1
print("IZZI v3.4 Replay Self-Test")
print("Archived body records checked:",checked)
print("Missing blob files:",bad)
print("Font bodies:",fonts," suspicious:",fontbad)
print("Complete MP4 records:",media," suspicious:",mediabad)
for u,k in missing[:30]:print("  MISSING BLOB",k,u)
print("PASS" if not (bad or fontbad or mediabad) else "CHECK REQUIRED")

raise SystemExit(bool(bad or fontbad or mediabad))
