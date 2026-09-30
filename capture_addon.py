import hashlib,mimetypes,json
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from mitmproxy import http
from config import *
from import_har import load as load_json,save,metadata,RX
from range_assembler import add_range,register_complete
from media_mapping import add_media
from capture_session import event
from capture_observed import observe
from active_lesson import set_active, clear as clear_active
from cache_bust_recovery import canonical_url,is_recovery_url,note as note_recovery

MAX_BODY=250*1024*1024

def allowed(host):
    h=(host or "").lower()
    return h=="izzi.digital" or h.endswith(".izzi.digital")

def request(flow:http.HTTPFlow):
    p=urlparse(flow.request.pretty_url)

    # Local-only control endpoints: never forwarded upstream.
    if p.hostname=="bg.izzi.digital" and p.path=="/__offline_capture__/recovery_manifest":
        try:
            q=STATE_DIR/"recovery_manifest.json"
            body=q.read_bytes() if q.exists() else b'{"urls":[]}'
            flow.response=http.Response.make(200,body,{
                "Content-Type":"application/json; charset=utf-8",
                "Access-Control-Allow-Origin":"*","Cache-Control":"no-store"})
        except Exception as e:
            flow.response=http.Response.make(500,str(e).encode(),{"Access-Control-Allow-Origin":"*"})
        return

    if p.hostname=="bg.izzi.digital" and p.path=="/__offline_capture__/event":
        q=parse_qs(p.query); kind=(q.get("kind") or ["event"])[0]
        book=(q.get("book") or [None])[0]; lesson=(q.get("lesson") or [None])[0]
        url=(q.get("url") or [None])[0]
        event(kind,book,lesson,url)
        if kind in ("lesson-start","lesson-active"): set_active(book,lesson,url)
        elif kind in ("lesson-done","book-done"): clear_active()
        flow.response=http.Response.make(204,b"",{
            "Access-Control-Allow-Origin":"*","Cache-Control":"no-store"})
        return

    if allowed(p.hostname) and flow.request.method.upper() in ("GET","HEAD"):
        recovering=is_recovery_url(flow.request.pretty_url)
        removed=[]
        for h in ("if-none-match","if-modified-since"):
            if h in flow.request.headers:
                del flow.request.headers[h]; removed.append(h)
        flow.request.headers["Cache-Control"]="no-store, no-cache, max-age=0" if recovering else "no-cache"
        flow.request.headers["Pragma"]="no-cache"
        if removed: print("[FORCE FRESH]",",".join(removed),p.path)
        if recovering: print("[RECOVERY REQUEST]",canonical_url(flow.request.pretty_url))

def response(flow:http.HTTPFlow):
    if flow.response is None:return
    request_url=flow.request.pretty_url.split("#",1)[0]
    recovering=is_recovery_url(request_url)
    url=canonical_url(request_url) if recovering else request_url

    try:
        # Observe canonical URL so a recovered 200 clears 304-only classification.
        observe(url,flow.response.status_code,flow.response.headers.get("content-type",""),
                flow.request.headers.get("referer",""),len(flow.response.raw_content or b""))
    except Exception as e: print("[OBSERVE ERROR]",e)

    if not allowed(flow.request.host):return
    status=flow.response.status_code
    if status==304:
        if recovering: note_recovery(url,status,0)
        print("[CACHE 304]",url);return

    p=urlparse(url);ct=flow.response.headers.get("content-type","")
    is_mp4=p.path.lower().endswith(".mp4") or ct.lower().startswith("video/mp4")
    cr=flow.response.headers.get("content-range")
    if is_mp4:add_media(url,flow.request.headers.get("referer",""),dict(flow.request.headers))

    if is_mp4 and status==206 and cr:
        data=flow.response.raw_content or b""
        final=add_range(url,cr,data)
        if final:register_complete(url,final,ct or "video/mp4")
        decoded=False
    else:
        try:data=flow.response.content or b""
        except Exception:data=flow.response.raw_content or b""
        decoded=True

    if recovering:note_recovery(url,status,len(data or b""))
    if not data and status!=204:return
    if len(data)>MAX_BODY:
        print("[SKIP large]",len(data),url);return

    ext=Path(p.path).suffix or mimetypes.guess_extension(ct.split(";")[0]) or ".bin"
    ext=ext[:12] if ext.startswith(".") else ".bin"
    key="blobs/"+hashlib.sha256(data).hexdigest()+ext
    ARCHIVE_DIR.mkdir(parents=True,exist_ok=True);STATE_DIR.mkdir(parents=True,exist_ok=True)
    fp=ARCHIVE_DIR/key;fp.parent.mkdir(parents=True,exist_ok=True)
    if data and not fp.exists():fp.write_bytes(data)

    mp=load_json(URL_MAP_FILE,{})
    rec={"key":key,"content_type":ct,"status":status,"body_available":bool(data),
         "method":flow.request.method,"size":len(data),
         "source":"cache_bust_recovery_v3.3.3" if recovering else "capture_proxy_v3.2",
         "decoded":decoded}
    if cr:rec["content_range"]=cr
    if flow.request.headers.get("range"):rec["request_range"]=flow.request.headers["range"]
    arr=mp.setdefault(url,[]);sig=(key,flow.request.method,status,cr)
    if not any((x.get("key"),x.get("method"),x.get("status"),x.get("content_range"))==sig for x in arr):
        arr.append(rec);save(URL_MAP_FILE,mp)

    if p.netloc==SOURCE_HOST and flow.request.method=="GET":
        m=RX.match(p.path)
        if m and status==200 and data:
            bid,lid=m.groups();bt,lt=metadata(data,bid,lid)
            books=load_json(BOOKS_FILE,{})
            b=books.setdefault(bid,{"id":bid,"title":bt,"lessons":{}})
            if bt:b["title"]=bt
            b["lessons"][lid]={"id":lid,"path":p.path,"title":lt};save(BOOKS_FILE,books)
            print("[LESSON]",bid,lid,lt);return
    print("[RECOVERED]" if recovering else ("[RANGE]" if status==206 else "[CAPTURE]"),
          status,len(data),cr or "",url)
