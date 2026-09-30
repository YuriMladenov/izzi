import json,re,hashlib
from pathlib import Path
from config import ARCHIVE_DIR,STATE_DIR,URL_MAP_FILE
from import_har import load as load_json,save

RX=re.compile(r"^bytes\s+(\d+)-(\d+)/(\d+|\*)$",re.I)
STATE=STATE_DIR/"range_assembly"

def uid(url): return hashlib.sha256(url.encode("utf-8")).hexdigest()
def manifest_path(url):
    STATE.mkdir(parents=True,exist_ok=True); return STATE/(uid(url)+".json")
def merged(xs):
    xs=sorted((int(a),int(b)) for a,b in xs)
    out=[]
    for a,b in xs:
        if out and a<=out[-1][1]+1: out[-1][1]=max(out[-1][1],b)
        else: out.append([a,b])
    return out

def add_range(url,content_range,data):
    m=RX.match((content_range or "").strip())
    if not m or m.group(3)=="*": return None
    start,end,total=map(int,m.groups())
    if start<0 or end<start or end>=total or len(data)!=(end-start+1):
        print("[MP4 RANGE INVALID]",content_range,len(data),url); return None
    work=STATE/uid(url); work.mkdir(parents=True,exist_ok=True)
    part=work/f"{start}-{end}.part"
    if not part.exists() or part.stat().st_size!=len(data): part.write_bytes(data)
    mf=manifest_path(url)
    try: man=json.loads(mf.read_text(encoding="utf-8"))
    except: man={"url":url,"total":total,"ranges":[]}
    man["total"]=total
    if not any(int(x[0])==start and int(x[1])==end for x in man["ranges"]):
        man["ranges"].append([start,end,str(part)])
    mf.write_text(json.dumps(man,ensure_ascii=False,indent=2),encoding="utf-8")
    cov=merged((x[0],x[1]) for x in man["ranges"])
    covered=sum(b-a+1 for a,b in cov)
    print(f"[MP4 COVERAGE] {covered}/{total} ({covered*100/total:.1f}%)",url)
    if cov!=[[0,total-1]]: return None

    final=ARCHIVE_DIR/"assembled"/(uid(url)+".mp4"); final.parent.mkdir(parents=True,exist_ok=True)
    tmp=final.with_suffix(".tmp")
    pos=0
    with tmp.open("wb") as out:
        for a,b,fp in sorted(man["ranges"],key=lambda x:(int(x[0]),int(x[1]))):
            a,b=int(a),int(b)
            if b<pos: continue
            if a>pos: raise RuntimeError("gap in verified coverage")
            raw=Path(fp).read_bytes(); off=max(0,pos-a)
            out.write(raw[off:]); pos=b+1
            if pos>=total: break
    if tmp.stat().st_size!=total:
        tmp.unlink(missing_ok=True); return None
    tmp.replace(final); print("[MP4 COMPLETE]",total,url); return final

def register_complete(url,path,content_type="video/mp4"):
    mp=load_json(URL_MAP_FILE,{})
    rel=str(path.relative_to(ARCHIVE_DIR)).replace("\\","/")
    rec={"key":rel,"content_type":content_type or "video/mp4","status":200,
         "body_available":True,"method":"GET","size":path.stat().st_size,
         "source":"assembled_ranges","complete":True,"decoded":True}
    arr=mp.setdefault(url,[])
    if not any(x.get("key")==rel and x.get("complete") for x in arr): arr.append(rec)
    save(URL_MAP_FILE,mp)
