import json,time
from pathlib import Path
from config import STATE_DIR
P=STATE_DIR/"capture_session.json"

def load():
    try:return json.loads(P.read_text(encoding="utf-8"))
    except:return {"visits":[]}

def save(x):
    P.parent.mkdir(parents=True,exist_ok=True)
    P.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")

def event(kind,book=None,lesson=None,url=None,extra=None):
    x=load()
    x.setdefault("visits",[]).append({
        "time":time.strftime("%Y-%m-%d %H:%M:%S"),"kind":kind,
        "book":book,"lesson":lesson,"url":url,"extra":extra or {}
    })
    save(x)
