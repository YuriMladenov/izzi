import json,time,uuid
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from config import STATE_DIR
P=STATE_DIR/"cache_bust_recovery.json"
MARKER="__izzi_offline_recover"
SKIP_EXT={".mp4",".mp3",".webm",".ogg",".m4a",".wav"}
def load():
    try:return json.loads(P.read_text(encoding="utf-8"))
    except:return {"attempts":{}}
def save(x):
    P.parent.mkdir(parents=True,exist_ok=True)
    P.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")
def canonical_url(url):
    p=urlsplit(url)
    q=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if k!=MARKER]
    return urlunsplit((p.scheme,p.netloc,p.path,urlencode(q,doseq=True),""))
def is_recovery_url(url):
    return any(k==MARKER for k,v in parse_qsl(urlsplit(url).query,keep_blank_values=True))
def eligible(url):
    p=urlsplit(url); h=(p.hostname or "").lower()
    return p.scheme in ("http","https") and (h=="izzi.digital" or h.endswith(".izzi.digital")) and Path(p.path).suffix.lower() not in SKIP_EXT
def note(original,status,size=0):
    x=load(); x.setdefault("attempts",{}).setdefault(original,[]).append(
        {"time":time.time(),"status":int(status),"size":int(size or 0)})
    save(x)
