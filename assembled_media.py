from pathlib import Path
from urllib.parse import urlparse
from config import ARCHIVE_DIR, URL_MAP_FILE, SOURCE_HOST
from archive_state import load
import threading
LOCK=threading.RLock();CACHED=None
from replay_resolver import usable_body

def _valid(r):
    if not (r.get("complete") and r.get("body_available") and r.get("key")):
        return False
    return usable_body(r,ARCHIVE_DIR,'.mp4') and (ARCHIVE_DIR/r['key']).stat().st_size>0

def build_index():
    with LOCK:return _build_index()

def _build_index():
    global CACHED
    m=load(URL_MAP_FILE,{})
    if CACHED and CACHED[0] is m:return CACHED[1],CACHED[2]
    exact={}
    path={}
    for u,rs in m.items():
        pu=urlparse(u)
        if Path(pu.path).suffix.lower()!=".mp4": continue
        for r in rs:
            if not _valid(r): continue
            # assembled_ranges is preferred, but any explicitly complete body is acceptable.
            score=(int(r.get("source")=="assembled_ranges"),int(r.get("size") or 0))
            item={"url":u,"record":r,"score":score}
            if u not in exact or score>exact[u]["score"]: exact[u]=item
            k=(pu.netloc.lower(),pu.path)
            if k not in path or score>path[k]["score"]: path[k]=item
    CACHED=(m,exact,path)
    return exact,path

def resolve(request_url):
    exact,paths=build_index()
    if request_url in exact and _valid(exact[request_url]["record"]):return exact[request_url],"exact"
    p=urlparse(request_url)
    k=(p.netloc.lower(),p.path)
    if k in paths and _valid(paths[k]["record"]):return paths[k],"path"
    # Local replay URLs are represented as SOURCE_HOST in the archive.
    if not p.netloc:
        k=(SOURCE_HOST,p.path)
        if k in paths and _valid(paths[k]["record"]):return paths[k],"local-path"
    return None,None
