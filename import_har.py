import base64,hashlib,html,json,mimetypes,re,sys,time,os,tempfile
from pathlib import Path
from urllib.parse import urlparse
from config import *
RX=re.compile(r"^/DOS/(\d+)/(\d+)\.html$")
SENSITIVE={"authorization","proxy-authorization","cookie","set-cookie","x-api-key","x-auth-token","x-csrf-token","x-xsrf-token"}
def load(p,d):
    try:return json.loads(Path(p).read_text(encoding="utf-8"))
    except FileNotFoundError:return d
def save(p,o):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    # Readers see either the old complete JSON or the new complete JSON.
    # Never truncate the live URL map while replay is reading it.
    fd,tmp=tempfile.mkstemp(prefix='.'+p.name+'-',suffix='.tmp',dir=p.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(o,stream,ensure_ascii=False,indent=2)
            stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,p)
    finally:
        Path(tmp).unlink(missing_ok=True)
def body(c):
    if c.get("text") is None:return None
    try:return base64.b64decode(c["text"]) if c.get("encoding")=="base64" else c["text"].encode()
    except:return None
def parse_dos_data(data):
    """Extract the embedded `var dosData = {...};` JSON without swallowing page JS."""
    text=data.decode("utf-8",errors="ignore")
    marker=re.search(r"\bvar\s+dosData\s*=\s*",text)
    if not marker:return {}
    i=marker.end()
    dec=json.JSONDecoder()
    try:
        obj,_=dec.raw_decode(text[i:])
        return obj if isinstance(obj,dict) else {}
    except Exception:
        return {}

def clean_text(value):
    if not isinstance(value,str):return ""
    value=html.unescape(value)
    value=re.sub(r"<[^>]+>"," ",value)
    return re.sub(r"\s+"," ",value).strip()

def metadata(data,bid,lid):
    dos=parse_dos_data(data)
    book=clean_text(dos.get("publicationName") or dos.get("dosName"))
    lesson=clean_text(dos.get("unitName") or dos.get("title"))
    # Safe fallback only: never capture arbitrary script/JSON through an HTML tag.
    if not lesson:
        text=data.decode("utf-8",errors="ignore")
        m=re.search(r"<title[^>]*>([^<]{1,300})</title>",text,re.I|re.S)
        if m:lesson=clean_text(m.group(1))
    return book or ("Учебник "+bid), lesson or ("Урок "+lid)

def main():
    if len(sys.argv)<2:print("Плъзни HAR файл върху import_har.bat");return 1
    for d in (ARCHIVE_DIR,STATE_DIR,CAPTURES_DIR):d.mkdir(parents=True,exist_ok=True)
    mp=load(URL_MAP_FILE,{});books=load(BOOKS_FILE,{});imports=load(IMPORTS_FILE,[])
    for arg in sys.argv[1:]:
        hp=Path(arg);h=json.loads(hp.read_text(encoding="utf-8"));entries=h.get("log",{}).get("entries",[]);n=0
        for e in entries:
            req=e.get("request",{});res=e.get("response",{});u=req.get("url","")
            if not u.startswith(("http://","https://")):continue
            p=urlparse(u);u=p._replace(fragment="").geturl();data=body(res.get("content",{}))
            if data is None:continue
            ct=res.get("content",{}).get("mimeType") or "";ext=Path(p.path).suffix or mimetypes.guess_extension(ct.split(";")[0]) or ".bin"
            key="blobs/"+hashlib.sha256(data).hexdigest()+ext[:12];f=ARCHIVE_DIR/key;f.parent.mkdir(parents=True,exist_ok=True)
            if not f.exists():f.write_bytes(data)
            rec={"key":key,"content_type":ct,"status":res.get("status",200),"body_available":True,"method":req.get("method","GET"),"size":len(data)}
            arr=mp.setdefault(u,[])
            if not any(x.get("key")==key and x.get("method")==rec["method"] for x in arr):arr.append(rec)
            m=RX.match(p.path) if p.netloc==SOURCE_HOST else None
            if m:
                bid,lid=m.groups()
                book_title,lesson_title=metadata(data,bid,lid)
                b=books.setdefault(bid,{"id":bid,"title":book_title,"lessons":{}})
                # Upgrade a placeholder title when richer metadata is found later.
                if book_title and (b.get("title","").startswith("Учебник ") or b.get("title")!=book_title):
                    b["title"]=book_title
                b["lessons"][lid]={"id":lid,"path":p.path,"title":lesson_title}
            n+=1
        # sanitized capture
        for e in h.get("log",{}).get("entries",[]):
            for side in ("request","response"):
                obj=e.get(side,{})
                obj["headers"]=[x for x in obj.get("headers",[]) if x.get("name","").lower() not in SENSITIVE]
                obj.pop("cookies",None)
            if "postData" in e.get("request",{}):e["request"]["postData"]={"_removed":True}
        out=CAPTURES_DIR/(hp.stem+"_"+time.strftime("%Y%m%d_%H%M%S")+"_sanitized.har")
        out.write_text(json.dumps(h,ensure_ascii=False),encoding="utf-8")
        imports.append({"file":hp.name,"time":time.strftime("%Y-%m-%d %H:%M:%S"),"entries":len(entries),"bodies":n})
        print("Imported",hp.name,":",n,"bodies")
    save(URL_MAP_FILE,mp);save(BOOKS_FILE,books);save(IMPORTS_FILE,imports)
    print("Books:",len(books),"Unique URLs:",len(mp));print("Additive import complete.")
if __name__=="__main__":raise SystemExit(main())
