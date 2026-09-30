import json,re
from urllib.parse import urlparse
from config import STATE_DIR
from active_lesson import get_active

P=STATE_DIR/"media_map.json"
LESSON_RX=re.compile(r"/DOS/(\d+)/(\d+)\.html(?:$|[?#])")
BLOCK_RX=re.compile(r"(?:block|component|id)[^0-9]{0,8}([0-9]{4,})",re.I)

def load():
    try:return json.loads(P.read_text(encoding="utf-8"))
    except:return {"lessons":{}}

def save(x):
    P.parent.mkdir(parents=True,exist_ok=True)
    P.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")

def lesson_from_referer(ref):
    try:
        m=LESSON_RX.search(urlparse(ref or "").path)
        return (m.group(1),m.group(2)) if m else None
    except:return None

def add_media(url,referer,request_headers=None):
    lesson=lesson_from_referer(referer)
    source="referer"
    if not lesson:
        a=get_active()
        if a:
            lesson=(str(a["book"]),str(a["lesson"]))
            source="active-lesson"
    if not lesson:
        return False
    book,lid=lesson
    x=load(); lessons=x.setdefault("lessons",{})
    key=f"{book}/{lid}"
    e=lessons.setdefault(key,{"book":book,"lesson":lid,"media":[]})
    headers=dict(request_headers or {})
    text=" ".join([referer or ""]+[str(k)+" "+str(v) for k,v in headers.items()])
    blocks=sorted(set(BLOCK_RX.findall(text)))
    item={"url":url,"referer":referer,"blocks":blocks,
          "strict":True,"mapping_source":source}
    old=next((i for i in e["media"] if i.get("url")==url),None)
    if old:
        old.update(item)
    else:
        e["media"].append(item)
    save(x)
    return True

def lesson_media(book,lid):
    """Return strict media record dictionaries for one exact lesson."""
    e=load().get("lessons",{}).get(f"{book}/{lid}",{})
    return [i for i in e.get("media",[])
            if isinstance(i,dict) and i.get("url") and i.get("strict")]
