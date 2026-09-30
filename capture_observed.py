import json,time,re
from urllib.parse import urlparse
from config import STATE_DIR
P=STATE_DIR/"capture_observed.json"
LESSON_RX=re.compile(r"/DOS/(\d+)/(\d+)\.html")

def load():
    try:return json.loads(P.read_text(encoding="utf-8"))
    except:return {"requests":{}}

def save(x):
    P.parent.mkdir(parents=True,exist_ok=True)
    P.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")

def observe(url,status,ctype="",referer="",size=0):
    p=urlparse(url); path=p.path
    if not (p.hostname=="izzi.digital" or (p.hostname or "").endswith(".izzi.digital")): return
    x=load(); q=x.setdefault("requests",{})
    key=url
    rec=q.setdefault(key,{"url":url,"path":path,"seen":0,"statuses":[],"content_types":[],"referers":[],"max_size":0})
    rec["seen"]+=1
    if status not in rec["statuses"]: rec["statuses"].append(status)
    if ctype and ctype not in rec["content_types"]: rec["content_types"].append(ctype)
    if referer and referer not in rec["referers"] and len(rec["referers"])<12: rec["referers"].append(referer)
    rec["max_size"]=max(rec["max_size"],int(size or 0))
    rec["last_seen"]=time.strftime("%Y-%m-%d %H:%M:%S")
    save(x)
