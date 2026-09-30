import json,time
from config import STATE_DIR

P=STATE_DIR/"active_lesson.json"

def set_active(book=None,lesson=None,url=None):
    P.parent.mkdir(parents=True,exist_ok=True)
    P.write_text(json.dumps({
        "book":book,"lesson":lesson,"url":url,
        "time":time.time()
    },ensure_ascii=False,indent=2),encoding="utf-8")

def clear():
    set_active(None,None,None)

def get_active(max_age=45):
    try:
        x=json.loads(P.read_text(encoding="utf-8"))
        if time.time()-float(x.get("time",0))>max_age:
            return None
        if x.get("book") and x.get("lesson"):
            return x
    except:
        pass
    return None
