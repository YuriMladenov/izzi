import json,time,re,threading
from import_har import save as atomic_save
from urllib.parse import urlparse
from config import STATE_DIR
P=STATE_DIR/"capture_observed.json"
LESSON_RX=re.compile(r"/DOS/(\d+)/(\d+)\.html")
LOCK=threading.RLock()
CACHED=None
DIRTY=False
LAST_FLUSH=0
FLUSH_INTERVAL=2

def signature():
    try:
        stat=P.stat();return str(P.resolve()),stat.st_ino,stat.st_size,stat.st_mtime_ns
    except FileNotFoundError:return str(P.resolve()),None

def load():
    try:return json.loads(P.read_text(encoding="utf-8"))
    except:return {"requests":{}}

def save(x):
    atomic_save(P,x)

def flush(force=True):
    """Only diagnostics are buffered; resource bodies/indexes commit immediately."""
    global CACHED,DIRTY,LAST_FLUSH
    with LOCK:
        if not DIRTY or CACHED is None:return
        if signature()!=CACHED[0]:CACHED=None;DIRTY=False;return
        if not force and time.monotonic()-LAST_FLUSH<FLUSH_INTERVAL:return
        save(CACHED[1]);CACHED=(signature(),CACHED[1]);DIRTY=False;LAST_FLUSH=time.monotonic()

def observe(url,status,ctype="",referer="",size=0):
    global CACHED,DIRTY
    p=urlparse(url); path=p.path
    if not (p.hostname=="izzi.digital" or (p.hostname or "").endswith(".izzi.digital")): return
    with LOCK:
        stamp=signature()
        if CACHED is None or stamp!=CACHED[0]:CACHED=(stamp,load())
        x=CACHED[1];q=x.setdefault("requests",{})
        rec=q.setdefault(url,{"url":url,"path":path,"seen":0,"statuses":[],"content_types":[],"referers":[],"max_size":0})
        rec["seen"]+=1
        if status not in rec["statuses"]: rec["statuses"].append(status)
        if ctype and ctype not in rec["content_types"]: rec["content_types"].append(ctype)
        if referer and referer not in rec["referers"] and len(rec["referers"])<12: rec["referers"].append(referer)
        rec["max_size"]=max(rec["max_size"],int(size or 0))
        rec["last_seen"]=time.strftime("%Y-%m-%d %H:%M:%S")
        DIRTY=True;flush(force=False)
