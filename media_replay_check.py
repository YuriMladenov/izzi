import json
from pathlib import Path
from urllib.parse import urlparse
from config import *
from import_har import load

m=load(URL_MAP_FILE,{})
rows=[]
for u,rs in m.items():
    if Path(urlparse(u).path).suffix.lower()!=".mp4": continue
    complete=[r for r in rs if r.get("complete") and r.get("body_available") and r.get("key")]
    partial=[r for r in rs if r.get("status")==206]
    if complete:
        r=complete[-1]; f=ARCHIVE_DIR/r["key"]
        rows.append(("COMPLETE",f.stat().st_size if f.exists() else -1,len(partial),u,r["key"]))
    else:
        rows.append(("PARTIAL",0,len(partial),u,""))
print("IZZI v3.2.1 Media Replay Check")
print("MP4 URLs:",len(rows))
print("Complete:",sum(1 for x in rows if x[0]=="COMPLETE"))
print("Partial only:",sum(1 for x in rows if x[0]=="PARTIAL"))
for state,size,n,u,key in rows:
    print(f"[{state}] size={size} ranges={n}")
    print(" ",u)
    if key: print("  ->",key)
