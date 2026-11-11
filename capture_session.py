import json,time,threading
from import_har import save as atomic_save
LOCK=threading.RLock()
from pathlib import Path
from config import STATE_DIR
P=STATE_DIR/"capture_session.json"

def load():
    try:return json.loads(P.read_text(encoding="utf-8"))
    except:return {"visits":[]}

def save(x):
    atomic_save(P,x)

def event(kind,book=None,lesson=None,url=None,extra=None):
    from capture_observed import flush
    flush(force=kind in ('lesson-done','lesson-incomplete','book-done','book-incomplete'))
    with LOCK:
        _append(kind,book,lesson,url,extra)

def _append(kind,book,lesson,url,extra):
    x=load()
    x.setdefault("visits",[]).append({
        "time":time.strftime("%Y-%m-%d %H:%M:%S"),"kind":kind,
        "book":book,"lesson":lesson,"url":url,"extra":extra or {}
    })
    save(x)
