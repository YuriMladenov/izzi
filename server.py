import html,json,mimetypes,re,time
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import quote,unquote,urlparse
from config import *
from media_mapping import lesson_media
from assembled_media import resolve as resolve_assembled

TEXT={"application/javascript","application/x-javascript","application/json","application/xml","image/svg+xml"}
DOC_EXT={".pdf",".doc",".docx",".xls",".xlsx",".ppt",".pptx",".zip",".rar",".7z",".txt",".rtf",".odt",".ods",".odp",".epub"}
MEDIA_EXT={".mp3",".wav",".ogg",".m4a",".mp4",".webm",".mov"}
IMAGE_EXT={".jpg",".jpeg",".png",".gif",".svg",".webp"}
FONT_EXT={".woff",".woff2",".ttf",".otf",".eot"}
FILE_EXT=DOC_EXT|MEDIA_EXT|IMAGE_EXT


# v3.4: explicit MIME types important for Firefox offline replay.
MIME_OVERRIDES={
    ".woff2":"font/woff2",".woff":"font/woff",".ttf":"font/ttf",".otf":"font/otf",
    ".svg":"image/svg+xml",".js":"application/javascript",".mjs":"application/javascript",
    ".css":"text/css",".json":"application/json",".mp4":"video/mp4",".webm":"video/webm",
    ".mp3":"audio/mpeg",".ogg":"audio/ogg",".wasm":"application/wasm",
}
def replay_mime(url, recorded=""):
    from urllib.parse import urlparse
    from pathlib import Path
    ext=Path(urlparse(url).path).suffix.lower()
    return MIME_OVERRIDES.get(ext) or recorded or "application/octet-stream"

def load(p,d):
    try:return json.loads(Path(p).read_text(encoding="utf-8"))
    except:return d

def score(r):
    if not r or not r.get("body_available") or not r.get("key"): return -10000
    s=0
    if r.get("method","GET")=="GET": s+=100
    if r.get("complete"): s+=1000
    if r.get("status")==200: s+=300
    elif r.get("status")==206: s-=300
    if r.get("decoded"): s+=200
    if r.get("source")=="capture_proxy_v3.2": s+=100
    return s

def pick(rs):
    good=[r for r in (rs or []) if score(r)>-10000]
    return max(enumerate(good),key=lambda x:(score(x[1]),x[0]))[1] if good else None

def logical_path(path):
    """Normalize IZZI's two equivalent resource forms:
       /DOS/<book>/datastore/... <-> /datastore/...
       /DOS/<book>/profil/...    <-> /profil/...
       Lesson HTML keeps its /DOS/<book>/<lesson>.html identity.
    """
    mm=re.match(r"^/DOS/(\d+)/(.*)$",path)
    if not mm:return path
    tail="/"+mm.group(2)
    if tail.startswith(("/datastore/","/profil/","/_nuxt/")):
        return tail
    return path

def _izzi_host(h):
    h=(h or "").split(":",1)[0].lower()
    return h=="izzi.digital" or h.endswith(".izzi.digital")

def _canon_path(path):
    path=unquote(path or "/")
    mm=re.match(r"^/DOS/(\d+)/(.*)$",path)
    if mm:
        tail="/"+mm.group(2)
        if tail.startswith(("/datastore/","/profil/","/_nuxt/")):
            return tail
    return path

def find(m,host,path,q):
    """Resolve from the URL map itself.

    Exact URL is preferred. For IZZI resources we then compare canonical paths
    using parsed hostname (not netloc), so :443 / captured-host variations do
    not make an otherwise valid archived body unreachable.
    """
    requested_path=unquote(path)
    exact=[]
    for scheme in ("https","http"):
        for h in (host, host.split(":",1)[0]):
            u=f"{scheme}://{h}{requested_path}"+(("?"+q) if q else "")
            r=pick(m.get(u))
            if r: exact.append(r)
    if exact:return max(exact,key=score)

    want=_canon_path(requested_path)
    hits=[]
    for u,rs in m.items():
        try: pp=urlparse(u)
        except: continue
        # Never alias arbitrary external hosts. For the local bg.izzi.digital
        # route, any archived *.izzi.digital source is eligible.
        if _izzi_host(host):
            if not _izzi_host(pp.hostname): continue
        elif (pp.hostname or "").lower()!=(host or "").split(":",1)[0].lower():
            continue
        if _canon_path(pp.path)!=want: continue
        r=pick(rs)
        if not r: continue
        # Query is a preference, not a requirement. Cache-bust recovery stored
        # the body under the original canonical URL.
        qbonus=3 if pp.query==q else (2 if not q else 1)
        # Prefer the original bg host if several IZZI hosts share a path.
        hbonus=1 if (pp.hostname or "").lower()=="bg.izzi.digital" else 0
        hits.append((qbonus,hbonus,score(r),r,u))
    if hits:
        hits.sort(key=lambda x:x[:3],reverse=True)
        chosen=hits[0]
        if urlparse(chosen[4]).path!=requested_path:
            print("[CANONICAL REPLAY]",requested_path,"=>",urlparse(chosen[4]).path)
        return chosen[3]

    # Last-resort lesson lookup by exact book+lesson suffix, still only on IZZI.
    lm=re.match(r"^/DOS/(\d+)/(\d+)\.html$",requested_path)
    if lm and _izzi_host(host):
        suffix=f"/DOS/{lm.group(1)}/{lm.group(2)}.html"
        lessons=[]
        for u,rs in m.items():
            pp=urlparse(u)
            if _izzi_host(pp.hostname) and unquote(pp.path).endswith(suffix):
                r=pick(rs)
                if r: lessons.append((score(r),r,u))
        if lessons:
            lessons.sort(key=lambda x:x[0],reverse=True)
            print("[LESSON FALLBACK]",requested_path,"=>",lessons[0][2])
            return lessons[0][1]
    return None

def rewrite(b):
    # Called ONLY for already-decoded textual resources.
    t=b.decode("utf-8",errors="strict")
    pairs=(("https://bg.izzi.digital/","/"),("http://bg.izzi.digital/","/"),
           ("//bg.izzi.digital/","/"),
           ("https:\\/\\/bg.izzi.digital\\/","\\/"),
           ("http:\\/\\/bg.izzi.digital\\/","\\/"),
           ("\\/\\/bg.izzi.digital\\/","\\/"),
           ("https://api.izzi.digital/","/__host__/api.izzi.digital/"),
           ("http://api.izzi.digital/","/__host__/api.izzi.digital/"),
           ("//api.izzi.digital/","/__host__/api.izzi.digital/"),
           ("https:\\/\\/api.izzi.digital\\/","\\/__host__\\/api.izzi.digital\\/"),
           ("https://xapi.izzi.digital/","/__host__/xapi.izzi.digital/"),
           ("http://xapi.izzi.digital/","/__host__/xapi.izzi.digital/"),
           ("//xapi.izzi.digital/","/__host__/xapi.izzi.digital/"),
           ("https:\\/\\/xapi.izzi.digital\\/","\\/__host__\\/xapi.izzi.digital\\/"),
           ("https://www.googletagmanager.com/gtm.js","/__offline__/gtag.js"))
    for a,c in pairs:t=t.replace(a,c)
    return t.encode("utf-8")

def inject_media_map(b,path):
    m=re.match(r"^/DOS/(\d+)/(\d+)\.html$",path)
    if not m:return b
    bid,lid=m.groups(); media=lesson_media(bid,lid)
    if not media:return b
    t=b.decode("utf-8",errors="strict")
    # IZZI pages may contain fallback <source> tags whose declared type does not
    # match the .mp4 URL. Firefox rejects those before trying the resource.
    t=re.sub(r'(<source\b[^>]*\bsrc=["\'][^"\']+\.mp4(?:\?[^"\']*)?["\'][^>]*\btype=["\'])([^"\']+)(["\'])',
             lambda m:m.group(1)+"video/mp4"+m.group(3),t,flags=re.I)
    t=re.sub(r'(<source\b[^>]*\btype=["\'])([^"\']+)(["\'][^>]*\bsrc=["\'][^"\']+\.mp4(?:\?[^"\']*)?["\'])',
             lambda m:m.group(1)+"video/mp4"+m.group(3),t,flags=re.I)
    urls=[x.get("url") for x in media if isinstance(x,dict) and x.get("url")]
    local=[]
    for u in urls:
        q=urlparse(u)
        if q.netloc=="bg.izzi.digital": local.append(q.path+(("?"+q.query) if q.query else ""))
        else: local.append("/__host__/"+q.netloc+q.path+(("?"+q.query) if q.query else ""))
    payload=json.dumps({"book":bid,"lesson":lid,"media":local},ensure_ascii=False)
    shim=r"""<script>
window.__IZZI_OFFLINE_MEDIA__=PAYLOAD;
(function(){
  const M=window.__IZZI_OFFLINE_MEDIA__.media||[];
  function bad(v){return !v||v==="#"||v.endsWith(".html#")||v.endsWith(".html");}
  function fix(root){
    const nodes=(root||document).querySelectorAll("video,audio");
    nodes.forEach((el,i)=>{
      let src=el.getAttribute("src")||"";
      let sources=[...el.querySelectorAll("source")];
      let valid=src&&!bad(src);
      if(!valid) valid=sources.some(x=>{let v=x.getAttribute("src")||"";return v&&!bad(v)});
      if(!valid && M.length){
        let u=M[Math.min(i,M.length-1)];
        if(sources.length) sources[0].setAttribute("src",u); else el.setAttribute("src",u);
        try{el.load()}catch(e){}
        console.log("[IZZI OFFLINE MEDIA MAP]",i,u);
      }
    });
  }
  document.addEventListener("DOMContentLoaded",()=>{fix(document);setTimeout(()=>fix(document),500);setTimeout(()=>fix(document),2000)});
  new MutationObserver(()=>fix(document)).observe(document.documentElement,{subtree:true,childList:true});
})();
</script>""".replace("PAYLOAD",payload)
    pos=t.lower().rfind("</body>")
    t=t[:pos]+shim+t[pos:] if pos>=0 else t+shim
    return t.encode("utf-8")

def parse_range(value,total):
    if not value or not value.startswith("bytes="):return None
    spec=value[6:].split(",",1)[0].strip()
    if "-" not in spec:return None
    a,b=spec.split("-",1)
    try:
        if not a:
            n=int(b);return max(0,total-n),total-1
        a=int(a);b=int(b) if b else total-1
        if a>=total:return "invalid"
        return a,min(b,total-1)
    except:return None

def resource_stats(mapping,book_id=None):
    st={"documents":0,"media":0,"images":0,"fonts":0}
    for u,rs in mapping.items():
        pp=urlparse(u);r=pick(rs)
        if not r:continue
        ext=Path(pp.path).suffix.lower()
        if book_id and f"/publication/{book_id}/" not in pp.path and f"/DOS/{book_id}/" not in pp.path and ext not in FONT_EXT:continue
        if ext in DOC_EXT:st["documents"]+=1
        elif ext in MEDIA_EXT:st["media"]+=1
        elif ext in IMAGE_EXT:st["images"]+=1
        elif ext in FONT_EXT:st["fonts"]+=1
    return st

def progress_summary(book_id):
    f=PROGRESS_DIR/(str(book_id)+".jsonl")
    if not f.exists():return 0
    try:return sum(1 for x in f.open(encoding="utf-8") if x.strip())
    except:return 0
def missing_log():return STATE_DIR/"missing_resources.jsonl"

class H(BaseHTTPRequestHandler):
    def sendb(self,b,ct="application/octet-stream",status=200,extra=None):
        self.send_response(status);self.send_header("Content-Type",ct);self.send_header("Content-Length",str(len(b)))
        self.send_header("Cache-Control","no-store")
        for k,v in (extra or {}).items():self.send_header(k,v)
        self.end_headers()
        if self.command!="HEAD":self.wfile.write(b)

    def sendfile(self,f,ct):
        total=f.stat().st_size;rr=parse_range(self.headers.get("Range"),total)
        if rr=="invalid":
            self.send_response(416);self.send_header("Content-Range",f"bytes */{total}");self.end_headers();return
        if rr:
            a,b=rr;n=b-a+1
            self.send_response(206);self.send_header("Content-Type",ct);self.send_header("Accept-Ranges","bytes")
            self.send_header("Content-Range",f"bytes {a}-{b}/{total}");self.send_header("Content-Length",str(n))
            self.send_header("X-IZZI-Replay","complete-media-range")
            self.send_header("Cache-Control","no-store");self.end_headers()
            if self.command!="HEAD":
                with f.open("rb") as x:x.seek(a);self.wfile.write(x.read(n))
            return
        self.send_response(200);self.send_header("Content-Type",ct);self.send_header("Accept-Ranges","bytes")
        self.send_header("Content-Length",str(total));self.send_header("X-IZZI-Replay","complete-media")
        self.send_header("Cache-Control","no-store");self.end_headers()
        if self.command!="HEAD":self.wfile.write(f.read_bytes())

    def archive(self,m,host,path,q):
        # v3.4.2: complete assembled MP4 takes precedence over captured 206 chunks.
        if Path(unquote(path)).suffix.lower()==".mp4":
            full=("https://"+host+path)+(("?"+q) if q else "")
            ar=resolve_assembled(full)
            if not ar and _izzi_host(host):
                # Captured HTML can request /DOS/<book>/datastore/... while the
                # original media URL was /datastore/....
                cp=_canon_path(path)
                full2=("https://bg.izzi.digital"+cp)+(("?"+q) if q else "")
                ar=resolve_assembled(full2)
            if ar:
                af=Path(ar["path"]) if isinstance(ar,dict) and ar.get("path") else Path(ar)
                if af.exists():
                    print("[ASSEMBLED MEDIA REPLAY]",path)
                    return self.sendfile(af,"video/mp4")
        r=find(m,host,path,q)
        if not r:
            print("[MISS]",host,path,q);STATE_DIR.mkdir(parents=True,exist_ok=True)
            with missing_log().open("a",encoding="utf-8") as o:
                o.write(json.dumps({"time":time.strftime("%Y-%m-%d %H:%M:%S"),"host":host,"path":path,"query":q},ensure_ascii=False)+"\n")
            return self.sendb(b"Not captured","text/plain; charset=utf-8",404)
        f=ARCHIVE_DIR/r["key"]
        if not f.exists():return self.sendb(b"Missing blob","text/plain",404)
        ct=replay_mime(path, r.get("content_type") or mimetypes.guess_type(path)[0] or mimetypes.guess_type(f.name)[0] or "")
        mime=ct.split(";")[0].lower();ext=Path(path).suffix.lower()
        print("[REPLAY]",r.get("status"),r.get("source","?"),"decoded="+str(r.get("decoded")),r["key"],path)
        if ext in MEDIA_EXT or mime.startswith(("video/","audio/")):
            # Never replay an incomplete captured 206 chunk as if it were a complete file.
            if r.get("status")==206 and not r.get("complete"):
                print("[MEDIA INCOMPLETE]",path,r.get("content_range"))
                return self.sendb(b"Incomplete captured media range","text/plain; charset=utf-8",409)
            if ext==".mp4" and not mime.startswith("video/"):
                ct="video/mp4"
            print("[MEDIA REPLAY]","complete="+str(bool(r.get("complete"))),
                  "range="+str(self.headers.get("Range")),r["key"],path)
            return self.sendfile(f,ct)
        b=f.read_bytes()
        if mime.startswith("text/") or mime in TEXT or "javascript" in mime:
            try:
                b=rewrite(b)
                if path.lower().endswith(".html"): b=inject_media_map(b,path)
            except UnicodeDecodeError:
                print("[BAD TEXT BLOB]",r["key"],path)
                return self.sendb(b"Captured text resource is still compressed/corrupt. Recapture with v3.2 and Disable Cache.","text/plain; charset=utf-8",502)
        return self.sendb(b,ct)

    def route(self):
        p=urlparse(self.path);m=load(URL_MAP_FILE,{});books=load(BOOKS_FILE,{})
        if p.path=="/":
            items=[]
            for bid,b in sorted(books.items()):
                st=resource_stats(m,bid);pr=progress_summary(bid)
                info='%d урока · %d документа · %d медия · %d изображения · %d progress'%(len(b.get("lessons",{})),st["documents"],st["media"],st["images"],pr)
                items.append('<li><a href="/__book__/%s"><b>%s</b></a><br><small>ID %s · %s</small></li>'%(bid,html.escape(b.get("title","Учебник "+bid)),bid,html.escape(info)))
            page='<!doctype html><meta charset="utf-8"><title>IZZI Offline Library</title><h1>IZZI Offline Library v3.3.1</h1><p><a href="/__missing__">Липсващи ресурси</a></p><ul>'+''.join(items)+'</ul>'
            return self.sendb(page.encode(),"text/html; charset=utf-8")
        if p.path.startswith("/__book__/"):
            bid=p.path.split("/")[-1];b=books.get(bid)
            if not b:return self.sendb(b"Unknown book","text/plain",404)
            ls=sorted(b.get("lessons",{}).values(),key=lambda x:int(x["id"]))
            items=''.join('<li><a href="%s">%s</a> <small>(%s)</small></li>'%(html.escape(x["path"]),html.escape(x["title"]),x["id"]) for x in ls)
            return self.sendb(('<!doctype html><meta charset="utf-8"><h1>%s</h1><p><a href="/">← Библиотека</a></p><ol>%s</ol>'%(html.escape(b["title"]),items)).encode(),"text/html; charset=utf-8")
        if p.path=="/__offline__/gtag.js":
            return self.sendb(b"window.dataLayer=window.dataLayer||[];window.gtag=window.gtag||function(){window.dataLayer.push(arguments);};","application/javascript")
        if p.path=="/__missing__":
            events=[];seen=set();f=missing_log()
            if f.exists():
                for line in f.open(encoding="utf-8"):
                    try:e=json.loads(line)
                    except:continue
                    k=(e.get("host"),e.get("path"),e.get("query"))
                    if k not in seen:seen.add(k);events.append(e)
            rows=''.join('<li><code>%s%s</code></li>'%(html.escape(e.get("host","")+e.get("path","")),html.escape(("?"+e.get("query","")) if e.get("query") else "")) for e in events[-500:])
            return self.sendb(('<!doctype html><meta charset="utf-8"><h1>Липсващи ресурси (%d)</h1><ul>%s</ul>'%(len(events),rows)).encode(),"text/html; charset=utf-8")
        if p.path.startswith("/__host__/"):
            rest=p.path[len("/__host__/"):]
            if "/" not in rest:return self.sendb(b"Bad route","text/plain",400)
            host,tail=rest.split("/",1);return self.archive(m,unquote(host),"/"+tail,p.query)
        return self.archive(m,SOURCE_HOST,p.path,p.query)

    def do_GET(self):self.route()
    def do_HEAD(self):self.route()
    def progress(self):
        n=int(self.headers.get("Content-Length","0") or 0);raw=self.rfile.read(n) if n else b"";ref=self.headers.get("Referer","")
        mm=re.search(r"/DOS/(\d+)/",ref+" "+self.path);bid=mm.group(1) if mm else "general"
        PROGRESS_DIR.mkdir(parents=True,exist_ok=True);f=PROGRESS_DIR/(bid+".jsonl")
        e={"time":time.strftime("%Y-%m-%d %H:%M:%S"),"method":self.command,"path":self.path,"referer":ref,"body":raw.decode("utf-8",errors="replace")[:100000]}
        with f.open("a",encoding="utf-8") as o:o.write(json.dumps(e,ensure_ascii=False)+"\n")
        print("[PROGRESS]",bid,self.command,self.path);self.sendb(b'{"offline":true,"saved":true}',"application/json",200)
    def do_POST(self):self.progress()
    def do_PUT(self):self.progress()
    def do_PATCH(self):self.progress()
    def do_DELETE(self):self.progress()
    def log_message(self,fmt,*args):print("[HTTP]",fmt%args)

if __name__=="__main__":
    for d in (ARCHIVE_DIR,STATE_DIR,CAPTURES_DIR,PROGRESS_DIR):d.mkdir(parents=True,exist_ok=True)
    print(f"IZZI Offline Library v3.3.1: http://{HOST}:{PORT}/")
    ThreadingHTTPServer((HOST,PORT),H).serve_forever()
