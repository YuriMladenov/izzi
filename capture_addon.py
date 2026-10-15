import asyncio,hashlib,mimetypes,json,re,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse,parse_qs,urljoin
from mitmproxy import http
from config import *
from import_har import load as load_json,save,metadata,RX,update_entry
from range_assembler import add_range,register_complete,restore_archived
from collections import OrderedDict
from media_mapping import add_media
from capture_session import event
from capture_observed import observe
from active_lesson import set_active, clear as clear_active
from replay_resolver import find,pick,usable_body,complete_range
from cache_bust_recovery import canonical_url,is_recovery_url,note as note_recovery

import external_links
import capture_completion
import archive_db
import geogebra_runtime
import bundled_assets
from archive_storage import blob_key

def running():
    archive_db.initialize(STATE_DIR)
    external_links.hosts()

MISSING_ONLY=False
UPDATE_BOOK=''
UPDATE_UNTIL=0
STATIC_EXT={'.html','.htm','.js','.css','.json','.svg','.png','.jpg','.jpeg','.gif','.webp','.woff','.woff2','.ttf','.mp4','.mp3','.webm','.pdf','.sb3','.sb2','.zip','.exe','.ggb'}

MAX_BODY=250*1024*1024
# Session headers stay in proxy memory, scoped to the exact video URL.
VIDEO_HEADERS=OrderedDict()
SESSION_HEADERS=('Cookie','Authorization','Referer','Origin','User-Agent')

def allowed(host):
    h=(host or "").lower()
    return h=="izzi.digital" or h.endswith(".izzi.digital") or h in external_links.hosts() or h=="cdnjs.cloudflare.com"

# Hooks return an awaitable under mitmproxy, while synchronous diagnostic callers
# retain the same API. A single archive worker preserves response write ordering.
WORKERS={}
def worker(name):
    if name not in WORKERS:WORKERS[name]=ThreadPoolExecutor(max_workers=1,thread_name_prefix='izzi-'+name)
    return WORKERS[name]

async def dispatch(name,function,flow):
    return await asyncio.get_running_loop().run_in_executor(worker(name),function,flow)

def request_sync(flow):
    with archive_db.read_session():_request(flow)

def request(flow:http.HTTPFlow):
    try:asyncio.get_running_loop()
    except RuntimeError:return request_sync(flow)
    p=urlparse(flow.request.pretty_url)
    if (p.hostname==SOURCE_HOST and p.path.startswith('/__offline_capture__/')) or flow.request.headers.get('X-IZZI-Resume') or MISSING_ONLY or '/GeoGebra/HTML5/' in p.path or '/fonts/' in p.path or '/sounds/' in p.path:
        return dispatch('control',request_sync,flow)
    return request_sync(flow)

def _request(flow):
    global MISSING_ONLY,UPDATE_BOOK,UPDATE_UNTIL
    p=urlparse(flow.request.pretty_url)
    if flow.request.headers.pop('X-IZZI-Resume',None):
        from video_resume import safe_url
        peer=getattr(flow.client_conn,'peername',None)
        if flow.request.method!='GET' or not peer or peer[0] not in ('127.0.0.1','::1') or not safe_url(flow.request.pretty_url):
            flow.response=http.Response.make(403,b'Local IZZI MP4 resume only');return
        flow.metadata['izzi_resume']=True
        target=canonical_url(flow.request.pretty_url)
        for name,value in VIDEO_HEADERS.get(target,{}).items():flow.request.headers[name]=value
        restore_archived(target)
        manifest=STATE_DIR/'range_assembly'/(hashlib.sha256(target.encode()).hexdigest()+'.json')
        if manifest.is_file():
            validator=load_json(manifest,{}).get('validator')
            if validator and not validator.startswith('W/'):flow.request.headers['If-Range']=validator

        row=find(load_json(URL_MAP_FILE,{}),p.hostname,p.path,p.query,lambda r:usable_body(r,ARCHIVE_DIR,'.mp4'))
        if row:
            body=(ARCHIVE_DIR/row['key']).read_bytes();size=len(body)
            match=re.fullmatch(r'bytes=(\d+)-(\d+)',flow.request.headers.get('Range',''))
            if match:
                start,end=int(match[1]),min(int(match[2]),size-1)
                if start<size:
                    flow.response=http.Response.make(206,body[start:end+1],{'Content-Type':'video/mp4','Content-Range':f'bytes {start}-{end}/{size}','X-IZZI-Archive':'1'});return
            flow.response=http.Response.make(200,body,{'Content-Type':'video/mp4','X-IZZI-Archive':'1'});return

    if p.hostname==SOURCE_HOST and p.path=="/__offline_capture__/youtube":
        import youtube_download
        q=parse_qs(p.query);identifier=(q.get('id') or [''])[0]
        data=youtube_download.status(identifier,start=q.get('start')==['1'])
        flow.response=http.Response.make(200,json.dumps(data).encode(),{'Content-Type':'application/json','Cache-Control':'no-store'})
        return
    if p.hostname==SOURCE_HOST and p.path=="/__offline_capture__/link_status":
        target=(parse_qs(p.query).get('url') or [''])[0]
        data=external_links.status(target,load_json(URL_MAP_FILE,{}),ARCHIVE_DIR)
        flow.response=http.Response.make(200,json.dumps(data).encode(),{'Content-Type':'application/json','Cache-Control':'no-store'})
        return
    if p.hostname==SOURCE_HOST and p.path=="/__offline_capture__/lesson_status":
        try:
            raw=flow.request.content or b''
            if flow.request.method!='POST' or len(raw)>256*1024:raise ValueError('Invalid status request')
            data=json.loads(raw)
            result=capture_completion.status(data.get('lesson',''),data.get('assets',[]),load_json(URL_MAP_FILE,{}),ARCHIVE_DIR)
            flow.response=http.Response.make(200,json.dumps(result).encode(),{'Content-Type':'application/json','Cache-Control':'no-store'})
        except (OSError,ValueError,AttributeError) as error:
            flow.response=http.Response.make(503,b'{"error":"Lesson archive status unavailable"}',{'Content-Type':'application/json'})
        return

    # Local-only control endpoints: never forwarded upstream.
    if p.hostname==SOURCE_HOST and p.path=="/__offline_capture__/image_status":
        requested=(parse_qs(p.query).get('url') or [''])[0]
        target=urlparse(requested)
        try:
            mapping=load_json(URL_MAP_FILE,{})
            ext=Path(target.path).suffix.lower()
            exact=parse_qs(p.query).get('exact')==['1']
            row=None
            if allowed(target.hostname):
                good=lambda r:usable_body(r,ARCHIVE_DIR,ext)
                row=pick(mapping.get(canonical_url(requested),[]),good) if exact else find(mapping,target.hostname or '',target.path,target.query,good)
            fallback=not exact and (bundled_assets.asset(target.hostname,target.path) or geogebra_runtime.asset(target.hostname,target.path))
            body=json.dumps({'capture':True,'available':bool(row or fallback)}).encode()
            flow.response=http.Response.make(200,body,{'Content-Type':'application/json','Cache-Control':'no-store'})
        except (OSError,ValueError):
            flow.response=http.Response.make(503,b'{"capture":true,"available":false}',{'Content-Type':'application/json'})
        return

    if p.hostname==SOURCE_HOST and p.path=='/__offline_capture__/geogebra_status':
        flow.response=http.Response.make(200,json.dumps({'installed':geogebra_runtime.installed()}).encode(),{'Content-Type':'application/json','Cache-Control':'no-store'})
        return

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
        extra={k:v[0] for k,v in q.items() if k in ("asset","reason","total","failed","title","number","module","section","order","missing_only")}
        if kind=='link-register':
            try:external_links.register(extra.get('asset',''))
            except ValueError:
                flow.response=http.Response.make(400,b'Unsupported external link');return
            capture_completion.expect(extra.get('asset',''),url)
        if kind=='book-start':MISSING_ONLY=False
        if kind=='update-mode':
            MISSING_ONLY=extra.get('missing_only')=='1';UPDATE_BOOK=str(book or '');UPDATE_UNTIL=time.monotonic()+600
        if kind=='lesson-active' and MISSING_ONLY:UPDATE_UNTIL=time.monotonic()+600
        if kind in ('book-done','book-incomplete'):MISSING_ONLY=False
        if kind=="lesson-start":capture_completion.start(url)
        event(kind,book,lesson,url,extra)
        if kind in ("lesson-start","lesson-active"): set_active(book,lesson,url)
        elif kind in ("lesson-done","lesson-incomplete","book-done","book-incomplete"): clear_active()
        flow.response=http.Response.make(204,b"",{
            "Access-Control-Allow-Origin":"*","Cache-Control":"no-store"})
        return

    capture_completion.watch(flow.request.pretty_url,flow.request.method,flow.request.headers.get('referer',''),getattr(flow,'id',id(flow)))
    runtime=(bundled_assets.asset(p.hostname,p.path) or geogebra_runtime.asset(p.hostname,p.path)) if flow.request.method=='GET' else None
    if runtime and not find(load_json(URL_MAP_FILE,{}),p.hostname,p.path,p.query,lambda row:usable_body(row,ARCHIVE_DIR,Path(p.path).suffix.lower())):
        ct='audio/wav' if p.path.lower().endswith('.wav') else mimetypes.guess_type(p.path)[0] or 'application/octet-stream'
        flow.response=http.Response.make(200,runtime.read_bytes(),{'Content-Type':ct,'Cache-Control':'no-store','X-IZZI-Archive':'1'})
        return

    if not getattr(flow,'metadata',{}).get('izzi_resume') and MISSING_ONLY and time.monotonic()<UPDATE_UNTIL and flow.request.method.upper()=='GET' and allowed(p.hostname):
        owner=re.search(r'/DOS/(\d+)/',p.path) or re.search(r'/DOS/(\d+)/',flow.request.headers.get('referer',''))
        scoped=(owner and owner[1]==UPDATE_BOOK) or (not owner and p.path.startswith(('/datastore/','/profil/','/assets/','/_nuxt/'))) or (p.hostname in external_links.hosts() and not p.hostname.endswith('izzi.digital'))
        ext=Path(p.path).suffix.lower()
        if scoped and ext in STATIC_EXT and not p.path.startswith('/api/'):
            mapping=load_json(URL_MAP_FILE,{})
            row=find(mapping,p.hostname,p.path,p.query,lambda r:usable_body(r,ARCHIVE_DIR,ext) and r.get('decoded',False))
            if row:
                data=(ARCHIVE_DIR/row['key']).read_bytes();headers={'Content-Type':row.get('content_type') or 'application/octet-stream','Cache-Control':'no-store','X-IZZI-Archive':'1'};status=200
                byte_range=re.fullmatch(r'bytes=(\d*)-(\d*)',flow.request.headers.get('range',''))
                if byte_range and data:
                    size=len(data);a,b=byte_range.groups();start=int(a) if a else max(0,size-int(b or size));end=min(size-1,int(b) if a and b else size-1)
                    if start<=end and start<size:data=data[start:end+1];status=206;headers['Content-Range']=f'bytes {start}-{end}/{size}'
                flow.response=http.Response.make(status,data,headers)
                print('[ARCHIVE REUSE]',p.path)
                return

    if allowed(p.hostname) and flow.request.method.upper() in ("GET","HEAD"):
        recovering=is_recovery_url(flow.request.pretty_url)
        removed=[]
        for h in ("if-none-match","if-modified-since"):
            if h in flow.request.headers:
                del flow.request.headers[h]; removed.append(h)
        flow.request.headers["cache-control"]="no-store, no-cache, max-age=0" if recovering else "no-cache"
        flow.request.headers["pragma"]="no-cache"
        if removed: print("[FORCE FRESH]",",".join(removed),p.path)
        if recovering: print("[RECOVERY REQUEST]",canonical_url(flow.request.pretty_url))

def response(flow:http.HTTPFlow):
    p=urlparse(flow.request.pretty_url)
    if flow.response is None or flow.response.headers.get('X-IZZI-Archive')=='1' or (p.hostname==SOURCE_HOST and p.path.startswith('/__offline_capture__/')) or not allowed(flow.request.host):
        capture_completion.finish(getattr(flow,'id',id(flow)));return
    try:asyncio.get_running_loop()
    except RuntimeError:return response_sync(flow)
    return dispatch('archive',response_sync,flow)

def response_sync(flow):
    try:
        with archive_db.read_session():_response(flow)
    finally:capture_completion.finish(getattr(flow,'id',id(flow)))

def _response(flow):
    if flow.response is None or flow.response.headers.get("X-IZZI-Archive")=="1":return
    control=urlparse(flow.request.pretty_url)
    if control.hostname==SOURCE_HOST and control.path.startswith("/__offline_capture__/"):return
    request_url=flow.request.pretty_url.split("#",1)[0]
    recovering=is_recovery_url(request_url)
    url=canonical_url(request_url) if recovering else request_url

    try:
        # Observe canonical URL so a recovered 200 clears 304-only classification.
        observe(url,flow.response.status_code,flow.response.headers.get("content-type",""),
                flow.request.headers.get("referer",""),len(flow.response.raw_content or b""))
    except Exception as e: print("[OBSERVE ERROR]",e)

    if not allowed(flow.request.host):return
    if not (flow.request.host=="izzi.digital" or flow.request.host.endswith(".izzi.digital")) and flow.request.method.upper() not in ("GET","HEAD"):return
    external_links.associate(url,flow.request.headers.get('referer',''))
    status=flow.response.status_code
    if status==304:
        if recovering: note_recovery(url,status,0)
        print("[CACHE 304]",url);return

    if 300<=status<400 and flow.response.headers.get('location'):
        external_links.associate(urljoin(url,flow.response.headers['location']),url)
    p=urlparse(url);ct=flow.response.headers.get("content-type","")
    is_mp4=p.path.lower().endswith(".mp4") or ct.lower().startswith("video/mp4")
    cr=flow.response.headers.get("content-range")
    if is_mp4 and status==206 and getattr(flow,'metadata',{}).get('izzi_resume') and flow.response.headers.get("content-encoding","identity").lower() not in ("identity",""):
        flow.response=http.Response.make(502,b'Compressed byte ranges cannot be resumed safely');return
    if is_mp4 and status in (200,206) and not getattr(flow,'metadata',{}).get('izzi_resume'):
        VIDEO_HEADERS[url]={name:flow.request.headers[name] for name in SESSION_HEADERS if name in flow.request.headers}
        VIDEO_HEADERS.move_to_end(url)
        while len(VIDEO_HEADERS)>256:VIDEO_HEADERS.popitem(last=False)
    if is_mp4:add_media(url,flow.request.headers.get("referer",""),dict(flow.request.headers))

    if is_mp4 and status==206 and cr:
        data=flow.response.raw_content or b""
        final=add_range(url,cr,data,flow.response.headers.get("etag") or flow.response.headers.get("last-modified"))
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
    key=blob_key(hashlib.sha256(data).hexdigest(),ext)
    ARCHIVE_DIR.mkdir(parents=True,exist_ok=True);STATE_DIR.mkdir(parents=True,exist_ok=True)
    fp=ARCHIVE_DIR/key;fp.parent.mkdir(parents=True,exist_ok=True)
    if data and not fp.exists():fp.write_bytes(data)

    rec={"key":key,"content_type":ct,"status":status,"body_available":bool(data),
         "method":flow.request.method,"size":len(data),
         "source":"cache_bust_recovery_v3.3.3" if recovering else "capture_proxy_v3.2",
         "decoded":decoded}
    external_links.discover(url,data,ct)
    if flow.response.headers.get("location"):rec["location"]=flow.response.headers["location"]
    if cr:rec["content_range"]=cr
    validator=flow.response.headers.get("etag") or flow.response.headers.get("last-modified")
    if validator:rec["validator"]=validator
    if flow.request.headers.get("range"):rec["request_range"]=flow.request.headers["range"]
    sig=(key,flow.request.method,status,cr)
    def append(arr):
        if not any((x.get("key"),x.get("method"),x.get("status"),x.get("content_range"))==sig for x in arr):arr.append(rec)
    update_entry(URL_MAP_FILE,url,append,[])

    if p.netloc==SOURCE_HOST and flow.request.method=="GET":
        m=RX.match(p.path)
        # A 206 may contain the entire HTML document. Partial ranges must not
        # create catalogue entries, but complete ones are valid replay lessons.
        if m and data and (status==200 or status==206 and complete_range(rec,len(data))):
            bid,lid=m.groups();bt,lt=metadata(data,bid,lid)
            def update_book(b):
                if bt:b["title"]=bt
                b.setdefault("lessons",{})[lid]={"id":lid,"path":p.path,"title":lt}
            update_entry(BOOKS_FILE,bid,update_book,{"id":bid,"title":bt,"lessons":{}})
            print("[LESSON]",bid,lid,lt);return
    print("[RECOVERED]" if recovering else ("[RANGE]" if status==206 else "[CAPTURE]"),
          status,len(data),cr or "",url)


def error(flow:http.HTTPFlow):
    capture_completion.finish(getattr(flow,'id',id(flow)))

def done():
    for pool in WORKERS.values():pool.shutdown(wait=True)
    WORKERS.clear()
    from capture_observed import flush
    flush()
