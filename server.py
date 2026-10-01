import html,json,mimetypes,re,time
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import quote,unquote,urlparse
from config import *
from media_mapping import lesson_media
from assembled_media import resolve as resolve_assembled
import progress_journal

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

from replay_resolver import (score,pick,logical_path,_izzi_host,_canon_path,find,book_ids,compatible_books,usable_body)

def usable_font(r):
    return usable_body(r,ARCHIVE_DIR,'.woff2')

def usable_image(r):
    return usable_body(r,ARCHIVE_DIR,'.png')

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
    # External YouTube playback is unavailable offline. Keep its API loader
    # local without simulating player events or fetching third-party cookies.
    t=re.sub(r'(?:(?:https?:)?//|https?:\\/\\/)(?:www\.)?youtube\.com(?:/|\\/)iframe_api\b',
             '/__offline__/youtube-api.js',t,flags=re.I)
    t=re.sub(r'(?:https?:)?//(?:www\.)?youtube\.com/s/player/[^"\'\s<>]+/www-widgetapi[^"\'\s<>]*\.js',
             '/__offline__/youtube-api.js',t,flags=re.I)
    t=re.sub(r'(?:https?:)?//(?:www\.)?(?:youtube\.com|youtube-nocookie\.com)/embed/',
             '/__offline__/external-media/',t,flags=re.I)
    return t.encode("utf-8")

def bad_media_source(value):
    value=(value or "").strip()
    return not value or value=="#" or urlparse(value).path.lower().endswith(".html")

class MediaPlaceholders(HTMLParser):
    """Remove invalid static media sources before the browser sees the tags.

    Preserve the document verbatim except for these attributes; the early
    lesson-scoped shim supplies missing sources as elements are parsed.
    """
    def __init__(self,text):
        super().__init__(convert_charrefs=False)
        self.text=text;self.edits=[];self.depth=0
        self.lines=[0]
        self.lines.extend(m.end() for m in re.finditer('\n',text))
    def handle_starttag(self,tag,attrs):
        if tag in {"video","audio"}:self.depth+=1
        if tag not in {"video","audio"} and not (tag=="source" and self.depth):return
        attrs=dict(attrs)
        if "src" not in attrs or not bad_media_source(attrs["src"]):return
        raw=self.get_starttag_text()
        attr_rx=re.compile(r'''\s+(?P<name>[^\s=/>]+)(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?''')
        cleaned=raw
        for attr in attr_rx.finditer(raw):
            if attr.group("name").lower()=="src":
                cleaned=raw[:attr.start()]+raw[attr.end():]
                break
        line,col=self.getpos();start=self.lines[line-1]+col
        self.edits.append((start,start+len(raw),cleaned))
    def handle_endtag(self,tag):
        if tag in {"video","audio"}:self.depth=max(0,self.depth-1)
    def handle_startendtag(self,tag,attrs):
        depth=self.depth
        self.handle_starttag(tag,attrs)
        self.depth=depth
    def clean(self):
        self.feed(self.text)
        text=self.text
        for start,end,replacement in reversed(self.edits):text=text[:start]+replacement+text[end:]
        return text

def inject_media_map(b,path):
    m=re.match(r"^/DOS/(\d+)/(\d+)\.html$",path)
    if not m:return b
    bid,lid=m.groups(); media=lesson_media(bid,lid)
    t=b.decode("utf-8",errors="strict")
    t=MediaPlaceholders(t).clean()
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
    payload=json.dumps({"book":bid,"lesson":lid,"media":local,
                       "blocks":[x.get("blocks",[]) for x in media]},ensure_ascii=False).replace("<","\\u003c")
    shim=r"""<script>
window.__IZZI_OFFLINE_MEDIA__=PAYLOAD;
(function(){
  const M=window.__IZZI_OFFLINE_MEDIA__.media||[];
  const B=window.__IZZI_OFFLINE_MEDIA__.blocks||[];
  function bad(v){
    if(!v||!v.trim()||v.trim()==="#")return true;
    try{return new URL(v,document.baseURI).pathname.toLowerCase().endsWith(".html");}catch(e){return true;}
  }
  function fix(root){
    if(document.readyState==="loading")return;
    const nodes=(root||document).querySelectorAll("video,audio");
    nodes.forEach((el,i)=>{
      let src=el.getAttribute("src")||"";
      let sources=[...el.querySelectorAll("source")];
      let valid=src&&!bad(src);
      if(!valid) valid=sources.some(x=>{let v=x.getAttribute("src")||"";return v&&!bad(v)});
      const audio=el.tagName==="AUDIO";
      const candidates=M.map((url,index)=>({url,index})).filter(x=>{
        const ext=new URL(x.url,document.baseURI).pathname.toLowerCase();
        return audio?/\.(mp3|wav|ogg|m4a)$/.test(ext):!/\.(mp3|wav|ogg|m4a)$/.test(ext);
      });
      const block=el.closest('[data-id], [id^="block-"]');
      const blockId=block&&(block.getAttribute("data-id")||(block.id||"").replace(/^block-/,""));
      let selected=candidates.find(x=>(B[x.index]||[]).map(String).includes(blockId));
      const sameKind=[...nodes].filter(x=>x.tagName===el.tagName);
      if(!selected && !candidates.some(x=>(B[x.index]||[]).length))selected=candidates[sameKind.indexOf(el)];
      if(!valid && selected){
        let u=selected.url;
        if(sources.length){
          el.removeAttribute("src");
          sources[0].setAttribute("src",u);
          if(new URL(u,document.baseURI).pathname.toLowerCase().endsWith(".mp4"))sources[0].setAttribute("type","video/mp4");
          sources.slice(1).forEach(x=>{if(bad(x.getAttribute("src")))x.removeAttribute("src");});
        }else el.setAttribute("src",u);
        try{el.load()}catch(e){}
        console.log("[IZZI OFFLINE MEDIA MAP]",i,u);
      }
    });
  }
  document.addEventListener("DOMContentLoaded",()=>{fix(document);setTimeout(()=>fix(document),500);setTimeout(()=>fix(document),2000)});
  new MutationObserver(()=>fix(document)).observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:["src"]});
})();
</script>""".replace("PAYLOAD",payload)
    # Observe parsing from the head, before media elements can try placeholder URLs.
    head=re.search(r'<head\b[^>]*>',t,re.I)
    pos=head.end() if head else 0
    t=t[:pos]+shim+t[pos:]
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
        context=book_ids(urlparse(self.headers.get("Referer","")).path)
        # Explicit book URLs remain navigable from another book's page.
        # Referer scope is only needed for paths that carry no book identity.
        book=next(iter(context)) if len(context)==1 and not book_ids(path) else None
        # v3.4.2: complete assembled MP4 takes precedence over captured 206 chunks.
        if Path(unquote(path)).suffix.lower()==".mp4":
            full=("https://"+host+path)+(("?"+q) if q else "")
            ar,match_kind=resolve_assembled(full)
            if not ar and _izzi_host(host):
                # Captured HTML can request /DOS/<book>/datastore/... while the
                # original media URL was /datastore/....
                cp=_canon_path(path)
                full2=("https://bg.izzi.digital"+cp)+(("?"+q) if q else "")
                ar,match_kind=resolve_assembled(full2)
            if ar and compatible_books(path,urlparse(ar["url"]).path,book):
                af=ARCHIVE_DIR/ar["record"]["key"]
                if af.is_file():
                    print("[ASSEMBLED MEDIA REPLAY]",path,match_kind)
                    return self.sendfile(af,"video/mp4")
        ext=Path(unquote(path)).suffix.lower()
        usable=lambda r:usable_body(r,ARCHIVE_DIR,ext)
        r=find(m,host,path,q,usable,book)
        # Retain real upstream errors when there is no usable body alternative.
        if not r and usable:
            error=find(m,host,path,q,None,book)
            if error and error.get('status')==206 and not error.get('complete') and ext in MEDIA_EXT:
                return self.sendb(b"Incomplete captured media range","text/plain; charset=utf-8",409)
            if error and int(error.get("status",200))>=400:
                f=ARCHIVE_DIR/error["key"]
                if f.is_file():
                    print("[UPSTREAM ERROR]",error["status"],path)
                    return self.sendb(f.read_bytes(),error.get("content_type") or "text/plain",error["status"])
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
        if p.path=="/__offline__/youtube-api.js":
            return self.sendb(b'/* YouTube player API is unavailable in offline replay. */',"application/javascript")
        if p.path=="/__offline__/progress":
            return self.sendb(json.dumps(progress_journal.summarize(PROGRESS_DIR),ensure_ascii=False).encode(),"application/json")
        if p.path.startswith("/__offline__/external-media/"):
            return self.sendb('<!doctype html><meta charset="utf-8"><p>Външното видео не е включено в офлайн архива.</p>'.encode(),"text/html; charset=utf-8")
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
        if self.headers.get("Transfer-Encoding"):
            self.close_connection=True
            return self.sendb(b'{"saved":false,"error":"transfer_encoding_unsupported"}',"application/json",501)
        try:n=int(self.headers.get("Content-Length","0") or 0)
        except ValueError:
            self.close_connection=True
            return self.sendb(b'{"saved":false,"error":"invalid_length"}',"application/json",400)
        if n<0 or n>progress_journal.MAX_WRITE:
            self.close_connection=True
            return self.sendb(b'{"saved":false,"error":"invalid_length"}',"application/json",413 if n>0 else 400)
        self.connection.settimeout(15)
        try:raw=self.rfile.read(n) if n else b""
        except TimeoutError:
            self.close_connection=True
            return self.sendb(b'{"saved":false,"error":"body_timeout"}',"application/json",408)
        if len(raw)!=n:
            return self.sendb(b'{"saved":false,"error":"incomplete_body"}',"application/json",400)
        try:
            bid=progress_journal.append(PROGRESS_DIR,self.command,self.path,self.headers.get("Referer",""),raw,self.headers.get("Content-Type",""))
        except OSError:
            return self.sendb(b'{"saved":false,"error":"journal_write_failed"}',"application/json",500)
        print("[PROGRESS]",bid,self.command,urlparse(self.path).path)
        self.sendb(b'{"offline":true,"saved":true}',"application/json",200)
    def do_POST(self):self.progress()
    def do_PUT(self):self.progress()
    def do_PATCH(self):self.progress()
    def do_DELETE(self):self.progress()
    def log_message(self,fmt,*args):print("[HTTP]",fmt%args)

if __name__=="__main__":
    for d in (ARCHIVE_DIR,STATE_DIR,CAPTURES_DIR,PROGRESS_DIR):d.mkdir(parents=True,exist_ok=True)
    print(f"IZZI Offline Library v3.3.1: http://{HOST}:{PORT}/")
    ThreadingHTTPServer((HOST,PORT),H).serve_forever()
