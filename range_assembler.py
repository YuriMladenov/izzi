import json,re,hashlib
from pathlib import Path
from config import ARCHIVE_DIR,STATE_DIR,URL_MAP_FILE
from import_har import load as load_json,save,update_entry

from archive_storage import assembled_key

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

def valid_part(path,start,end):
    path=Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size!=end-start+1:return False
    if start==0:
        with path.open('rb') as stream:header=stream.read(1024)
        if header.startswith(b'\x1f\x8b') or re.search(br'<(?:!doctype\s+html|html)\b',header,re.I):return False
    return True

def add_range(url,content_range,data,validator=None):
    m=RX.match((content_range or "").strip())
    if not m or m.group(3)=="*": return None
    start,end,total=map(int,m.groups())
    if start<0 or end<start or end>=total or len(data)!=(end-start+1):
        print("[MP4 RANGE INVALID]",content_range,len(data),url); return None
    work=STATE/uid(url); work.mkdir(parents=True,exist_ok=True)
    part=work/f"{start}-{end}.part"
    if not part.exists() or part.stat().st_size!=len(data) or part.read_bytes()!=data:part.write_bytes(data)
    mf=manifest_path(url)
    try: man=json.loads(mf.read_text(encoding="utf-8"))
    except: man={"url":url,"total":total,"ranges":[]}
    if man.get("total")!=total or (validator and man.get("validator") and validator!=man["validator"]):
        man={"url":url,"total":total,"ranges":[]}
    if validator:man["validator"]=validator
    man["total"]=total
    valid=[]
    for a,b,name in man.get('ranges',[]):
        source=Path(name)
        if not source.is_file():source=work/f'{a}-{b}.part'
        if 0<=int(a)<=int(b)<total and valid_part(source,int(a),int(b)):valid.append([int(a),int(b),str(source)])
    man['ranges']=valid
    if not any(int(x[0])==start and int(x[1])==end for x in man["ranges"]):
        man["ranges"].append([start,end,str(part)])
    save(mf,man)
    cov=merged((x[0],x[1]) for x in man["ranges"])
    covered=sum(b-a+1 for a,b in cov)
    print(f"[MP4 COVERAGE] {covered}/{total} ({covered*100/total:.1f}%)",url)
    if cov!=[[0,total-1]]: return None

    final=ARCHIVE_DIR/assembled_key(uid(url)); final.parent.mkdir(parents=True,exist_ok=True)
    tmp=final.with_suffix(".tmp")
    pos=0
    with tmp.open("wb") as out:
        for a,b,fp in sorted(man["ranges"],key=lambda x:(int(x[0]),int(x[1]))):
            a,b=int(a),int(b)
            if b<pos: continue
            if a>pos: raise RuntimeError("gap in verified coverage")
            source=Path(fp)
            if not source.is_file():source=work/f"{a}-{b}.part"
            if not source.is_file() or source.stat().st_size!=b-a+1:return None
            raw=source.read_bytes(); off=max(0,pos-a)
            out.write(raw[off:]); pos=b+1
            if pos>=total: break
    if tmp.stat().st_size!=total:
        tmp.unlink(missing_ok=True); return None
    tmp.replace(final); print("[MP4 COMPLETE]",total,url); return final

def register_complete(url,path,content_type="video/mp4"):
    rel=str(path.relative_to(ARCHIVE_DIR)).replace("\\","/")
    rec={"key":rel,"content_type":content_type or "video/mp4","status":200,
         "body_available":True,"method":"GET","size":path.stat().st_size,
         "source":"assembled_ranges","complete":True,"decoded":True}
    def append(arr):
        if not any(x.get("key")==rel and x.get("complete") for x in arr):arr.append(rec)
    update_entry(URL_MAP_FILE,url,append,[])


def restore_archived(url):
    """Seed matching archived 206 bodies, respecting the known resource version."""
    mapping=load_json(URL_MAP_FILE,{})
    man=load_json(manifest_path(url),{})
    candidates=[]
    for row in mapping.get(url,[]):
        match=RX.fullmatch(str(row.get('content_range','')))
        if row.get('status')!=206 or not row.get('body_available') or not match or match[3]=='*' or str(row.get('content_type','')).startswith(('text/','application/json')):continue
        candidates.append((row,match))
    total=man.get('total') or (int(candidates[-1][1][3]) if candidates else None)
    validator=man.get('validator') or (candidates[-1][0].get('validator') if candidates else None)
    selected={}
    for row,match in candidates:
        if int(match[3])!=total or (validator and row.get('validator')!=validator):continue
        selected[(int(match[1]),int(match[2]))]=row
    known={(int(a),int(b)) for a,b,_ in man.get('ranges',[])}
    for (start,end),row in selected.items():
        part=STATE/uid(url)/f'{start}-{end}.part'
        if (start,end) in known and valid_part(part,start,end):continue
        path=ARCHIVE_DIR/str(row.get('key',''))
        if not path.resolve().is_relative_to(ARCHIVE_DIR.resolve()) or not valid_part(path,start,end):continue
        final=add_range(url,row['content_range'],path.read_bytes(),validator)
        if final:register_complete(url,final)
    man=load_json(manifest_path(url),{})
    if man.get('ranges') and merged((a,b) for a,b,_ in man['ranges'])==[[0,man['total']-1]]:
        a,b,name=man['ranges'][0];path=Path(name)
        if not path.is_file():path=STATE/uid(url)/f'{a}-{b}.part'
        if path.is_file():
            final=add_range(url,f'bytes {a}-{b}/{man["total"]}',path.read_bytes(),man.get('validator'))
            if final:register_complete(url,final)
