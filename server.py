from collections.abc import Mapping
import html,json,mimetypes,re,time,hashlib,gzip,os,threading,sys
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import quote,unquote,urlparse,parse_qs
from config import *
from media_mapping import lesson_media
from assembled_media import resolve as resolve_assembled
import progress_journal
import library_catalog
import webui
import book_covers
import operations
import archive_db
import replay_cache
import geogebra_runtime
import admin_account
import bundled_assets
import project_maintenance
RUNNING_SERVER=None
RESTART_REQUESTED=False
from bundled_assets import bundled_font
from archive_state import load as load_archive_state

TEXT={"application/javascript","application/x-javascript","application/json","application/xml","image/svg+xml"}
DOC_EXT={".exe",".sb",".sb2",".sb3",".csv",".pdf",".doc",".docx",".xls",".xlsx",".ppt",".pptx",".zip",".rar",".7z",".txt",".rtf",".odt",".ods",".odp",".epub"}
MEDIA_EXT={".mp3",".wav",".ogg",".m4a",".mp4",".webm",".mov"}
IMAGE_EXT={".jpg",".jpeg",".png",".gif",".svg",".webp"}
FONT_EXT={".woff",".woff2",".ttf",".otf",".eot"}
DOC_EXT|={'.ggb'}
FILE_EXT=DOC_EXT|MEDIA_EXT|IMAGE_EXT


# v3.4: explicit MIME types important for Firefox offline replay.
MIME_OVERRIDES={
    '.ggb':'application/vnd.geogebra.file',
    ".woff2":"font/woff2",".woff":"font/woff",".ttf":"font/ttf",".otf":"font/otf",
    ".svg":"image/svg+xml",".js":"application/javascript",".mjs":"application/javascript",
    ".css":"text/css",".json":"application/json",".mp4":"video/mp4",".webm":"video/webm",
    ".mp3":"audio/mpeg",".wav":"audio/wav",".ogg":"audio/ogg",".wasm":"application/wasm",
}
def replay_mime(url, recorded=""):
    from urllib.parse import urlparse
    from pathlib import Path
    ext=Path(urlparse(url).path).suffix.lower()
    return MIME_OVERRIDES.get(ext) or recorded or "application/octet-stream"

def load(p,d):
    try:return json.loads(Path(p).read_text(encoding="utf-8"))
    except:return d

from replay_resolver import (score,pick,logical_path,_izzi_host,_canon_path,find,book_ids,compatible_books,usable_body,complete_body)

def usable_font(r):
    return usable_body(r,ARCHIVE_DIR,'.woff2')

def usable_image(r):
    return usable_body(r,ARCHIVE_DIR,'.png')


def rewrite(b,host=None,html_document=None):
    # Called ONLY for already-decoded textual resources.
    t=b.decode("utf-8",errors="strict")
    if html_document is None:html_document=t.lstrip().startswith('<')
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
    if not html_document and 'pdfPages:function' in t and 'pagesClientData' in t:
        # Offline lessons use the built-in reader (isExport=False), while the
        # flipbook still needs captured .html frames and relative page images.
        # Do not turn profile checks back on to obtain these export-only paths.
        t=re.sub(r'\(([$\w]+)\.\$root\.isExport\?"\.html":""\)', '".html"',t)
        t=re.sub(r'(pdfPages:function\(\)\{var [$\w]+=this,[$\w]+=)this\.\$root\.isExport\?"":"/"',r'\1""',t)
    if 'global-audio-player' in t and 'name:"alt-audio"' in t:
        # The browser resolves ./ and percent-encodes Cyrillic media URLs.
        # Compare resolved URLs, and allow pausing before metadata has loaded.
        t=re.sub(r'this\.\$player\.duration>0&&(!?)this\.\$player\.paused&&this\.\$player\.src\.indexOf\(([$A-Za-z_][$\w]*)\)>-1',
                 lambda m:m[1]+'this.$player.paused&&(new URL(this.$player.src,document.baseURI).href===new URL('+m[2]+',document.baseURI).href)',t)
    if 'youtu' in t.lower():
        # External YouTube playback is unavailable offline. Keep its API loader
        # local without simulating player events or fetching third-party cookies.
        origin=r'(?:https?://|//|https?:\\/\\/)'
        t=re.sub(origin+r'(?:www\.)?youtube\.com(?:/|\\/)iframe_api\b',
                 '/__offline__/youtube-api.js',t,flags=re.I)
        t=re.sub(r'(?:https?://|//)(?:www\.)?youtube\.com/s/player/[^"\'\s<>]+/www-widgetapi[^"\'\s<>]*\.js',
                 '/__offline__/youtube-api.js',t,flags=re.I)
        t=re.sub(r'(?:https?://|//)(?:www\.)?(?:youtube\.com|youtube-nocookie\.com)/embed/',
                 '/__offline__/external-media/',t,flags=re.I)
        slash=r'(?:/|\\/)'
        t=re.sub(r'https?:'+slash+slash+r'(?:www\.|m\.)?(?:youtube\.com|youtube-nocookie\.com)'+slash+r'(?:embed'+slash+r'|shorts'+slash+r'|watch\?v=)([A-Za-z0-9_-]{11})',lambda m:'/__offline__/external-media/'+m[1],t)
        t=re.sub(r'https?:'+slash+slash+r'(?:www\.)?youtu\.be'+slash+r'([A-Za-z0-9_-]{11})',lambda m:'/__offline__/external-media/'+m[1],t)
        def youtube_component(match):
            class Attributes(HTMLParser):
                values={}
                def handle_starttag(self,tag,attrs):self.values=dict(attrs)
            parser=Attributes();parser.feed('<youtube-player '+match[1]+'>')
            if any(name in parser.values for name in (':video-id','v-bind:video-id',':video-url','v-bind:video-url')):
                return match[0] # Vue resolves these props; the runtime shim supplies the local player.
            identifier=parser.values.get('video-id','')
            if not identifier:
                local=re.search(r'/__offline__/external-media/([A-Za-z0-9_-]{11})(?:[?&#/]|$)',parser.values.get('video-url',''))
                if local:identifier=local[1]
            if not re.fullmatch(r'[A-Za-z0-9_-]{11}',identifier):return '<p>Невалиден YouTube видео адрес.</p>'
            title=html.escape(parser.values.get('title',''))
            description=html.escape(re.sub(r'<[^>]*>',' ',html.unescape(parser.values.get('description',''))))
            return '<section class="offline-youtube" data-youtube-id="'+identifier+'">'+('<h3>'+title+'</h3>' if title else '')+('<p>'+description+'</p>' if description.strip() else '')+'<iframe title="'+(title or 'Видео')+'" src="/__offline__/external-media/'+identifier+'" style="width:100%;aspect-ratio:16/9;border:0" allowfullscreen loading="lazy"></iframe></section>'
        if html_document and '<youtube-player' in t:
            scripts=[(m.start(),m.end()) for m in re.finditer(r'<script\b[^>]*>[\s\S]*?</script\s*>',t,re.I)]
            t=re.sub(r'<youtube-player\b([^>]*?)>[\s\S]*?</youtube-player\s*>',lambda m:m[0] if any(a<=m.start()<b for a,b in scripts) else youtube_component(m),t,flags=re.I)
        import youtube_download
        def youtube_link(match):
            identifier=youtube_download.video_id(match[0])
            return '/__offline__/external-media/'+identifier if identifier else match[0]
        t=re.sub(r'(?:https?://|//)(?:www\.|m\.)?(?:youtube\.com|youtube-nocookie\.com|youtu\.be)/[^\s"\'<>\\]+',youtube_link,t)
    import external_links
    for external in external_links.hosts()|{'cdnjs.cloudflare.com'}:
        if external not in t:continue
        prefix='/__host__/'+external+'/'
        for origin in ('https://'+external+'/', 'http://'+external+'/', '//'+external+'/'):
            t=t.replace(origin,prefix).replace(origin.replace('/','\\/'),prefix.replace('/','\\/'))
    if host and not _izzi_host(host):
        prefix='/__host__/'+host+'/'
        t=re.sub(r'(["\'])/(?!/|__host__/)([^"\']+)',lambda m:m[1]+prefix+m[2],t)
        t=re.sub(r'url\(\s*/(?!/|__host__/)', 'url('+prefix,t,flags=re.I)
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
    # Use the captured lesson's built-in reader without an online profile check.
    marker=re.search(r'\bvar\s+dosData\s*=\s*',t)
    if marker:
        try:
            data,length=json.JSONDecoder().raw_decode(t[marker.end():])
            if isinstance(data,dict) and data.get('isExport') is True:
                data['isExport']=False
                safe=json.dumps(data,ensure_ascii=False).replace('<','\\u003c')
                t=t[:marker.end()]+safe+t[marker.end()+length:]
        except ValueError:pass
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
if(typeof window.baseUrl==='undefined')window.baseUrl='/';
(function(){
  const M=window.__IZZI_OFFLINE_MEDIA__.media||[];
  const B=window.__IZZI_OFFLINE_MEDIA__.blocks||[];
  function bad(v){
    if(!v||!v.trim()||v.trim()==="#")return true;
    try{return new URL(v,document.baseURI).pathname.toLowerCase().endsWith(".html");}catch(e){return true;}
  }
  function fix(root){
    if(document.readyState==="loading")return;
    fixYoutube();
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
    youtube_shim=Path(__file__).with_name('offline_youtube.js').read_text(encoding='utf-8')
    shim=shim.replace('  function fix(root){',youtube_shim+'\n  function fix(root){')
    # Observe parsing from the head, before media elements can try placeholder URLs.
    head=re.search(r'<head\b[^>]*>',t,re.I)
    pos=head.end() if head else 0
    # Also covers account names added by the archived page's scripts after load.
    style=('<style id="izzi-offline-user-name">'
           '.site-header .user-menu__name,#site-header #user-menu-label{display:none!important}'
           '</style>')
    t=t[:pos]+style+shim+t[pos:]
    # Keep navigation outside Vue's lesson root, including when its app fails
    # to mount. A relative origin path also works for readers over LAN.
    if 'id="izzi-library-return"' not in t:
        home=('<a id="izzi-library-return" href="/" target="_top" '
              'aria-label="Към началната страница на библиотеката" '
              'style="position:fixed!important;left:12px!important;bottom:12px!important;'
              'z-index:2147483647!important;display:inline-flex!important;align-items:center;'
              'min-height:44px;box-sizing:border-box;padding:10px 16px;border:1px solid #205fab;'
              'border-radius:10px;background:#fff;color:#205fab;font:600 16px/1.4 sans-serif;'
              'text-decoration:none;box-shadow:0 2px 10px #0003">← Библиотека</a>')
        body=re.search(r'<body\b[^>]*>',t,re.I)
        at=body.end() if body else len(t)
        t=t[:at]+home+t[at:]
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
        pp=urlparse(u);ext=Path(pp.path).suffix.lower()
        r=pick(rs,lambda row:usable_body(row,ARCHIVE_DIR,ext))
        if not r:continue
        if book_id and str(book_id) not in book_ids(pp.path):continue
        if ext in DOC_EXT:st["documents"]+=1
        elif ext in MEDIA_EXT:st["media"]+=1
        elif ext in IMAGE_EXT:st["images"]+=1
        elif ext in FONT_EXT:st["fonts"]+=1
    return st

def page_counts(mapping,book_id,book):
    pages=book.get('lessons',{})
    # This is an availability counter, not a full integrity audit. Reading all
    # lesson bodies here makes opening a book proportional to its total bytes.
    # Replay and diagnostics still validate the complete HTML on demand.
    available=sum(find(mapping,SOURCE_HOST,p.get('path') or f'/DOS/{book_id}/{lid}.html','',
                  lambda row:usable_body(row,ARCHIVE_DIR)) is not None
                  for lid,p in pages.items())
    return len(pages),available

def current_missing(events,mapping):
    missing=[];warnings=[];resolved=0;seen=set()
    for event in events:
        host=event.get('host',SOURCE_HOST);path=event.get('path','/');query=event.get('query','')
        if path.startswith('/__offline_capture__/'):continue
        key=(host,tuple(sorted(book_ids(path))),_canon_path(path))
        if key in seen:continue
        seen.add(key);ext=Path(path).suffix.lower()
        row=find(mapping,host,path,query,lambda r:usable_body(r,ARCHIVE_DIR,ext))
        if row or bundled_assets.asset(host,path) or geogebra_runtime.asset(host,path):resolved+=1;continue
        old=find(mapping,host,path,query)
        category='UPSTREAM 404 WARNING' if old and old.get('status')==404 else (
            'OPTIONAL' if ext=='.map' or path in ('/favicon.ico','/datastore/favicon.ico') else 'MISSING')
        item=(category,host+path)
        if category=='MISSING':missing.append(item)
        else:warnings.append(item)
    return missing,warnings,resolved

def progress_summary(book_id):
    f=PROGRESS_DIR/(str(book_id)+".jsonl")
    if not f.exists():return 0
    try:
        with f.open(encoding="utf-8") as stream:
            return sum(1 for x in stream if x.strip())
    except:return 0
def missing_log():return STATE_DIR/"missing_resources.jsonl"

class H(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    timeout=15
    def gzip_text(self,ctype):
        mime=ctype.split(';')[0].strip().lower()
        if not (mime.startswith('text/') or mime in TEXT):return False
        offers={}
        for item in self.headers.get('Accept-Encoding','').lower().split(','):
            parts=item.strip().split(';');quality=1.
            for parameter in parts[1:]:
                if parameter.strip().startswith('q='):
                    try:quality=float(parameter.strip()[2:])
                    except ValueError:quality=0.
            offers[parts[0].strip()]=quality
        return offers.get('gzip',offers.get('*',0))>0

    def cache_match(self,etag,vary=None):
        candidates=self.headers.get('If-None-Match','').split(',')
        matches=any(value.strip()=='*' or value.strip().removeprefix('W/')==etag for value in candidates)
        if self.command not in ('GET','HEAD') or not matches:return False
        self.send_response(304)
        self.send_header('ETag',etag)
        self.send_header('Cache-Control','private, max-age=0, must-revalidate')
        if vary:self.send_header('Vary',vary)
        self.end_headers()
        return True

    def send_cached(self,data,ctype,extra=None,etag=None,encoding=None):
        if encoding is None and len(data)>=1024 and self.gzip_text(ctype):
            data=gzip.compress(data,compresslevel=3,mtime=0);encoding='gzip';etag=None
        etag=etag or '"'+hashlib.sha256(data).hexdigest()+'"'
        if self.cache_match(etag,vary='Accept-Encoding'):return
        self.send_response(200)
        self.send_header('Content-Type',ctype)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('ETag',etag)
        self.send_header('Cache-Control','private, max-age=0, must-revalidate')
        self.send_header('Vary','Accept-Encoding')
        if encoding=='gzip':self.send_header('Content-Encoding','gzip')
        for key,value in (extra or {}).items():self.send_header(key,value)
        self.end_headers()
        if self.command!='HEAD':self.wfile.write(data)

    def sendb(self,b,ct="application/octet-stream",status=200,extra=None):
        encoded=status==200 and len(b)>=1024 and self.gzip_text(ct)
        if encoded:b=gzip.compress(b,compresslevel=3,mtime=0)
        self.send_response(status);self.send_header("Content-Type",ct);self.send_header("Content-Length",str(len(b)))
        self.send_header("Cache-Control","no-store")
        self.send_header('Vary','Accept-Encoding')
        if encoded:self.send_header('Content-Encoding','gzip')
        for k,v in (extra or {}).items():self.send_header(k,v)
        self.end_headers()
        if self.command!="HEAD":self.wfile.write(b)

    def sendfile(self,f,ct):
        stat=f.stat();total=stat.st_size
        etag='"'+hashlib.sha256((str(f)+str((stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,stat.st_ino))).encode()).hexdigest()+'"'
        if self.cache_match(etag):return
        requested=self.headers.get('Range')
        if requested and self.headers.get('If-Range') and self.headers['If-Range']!=etag:requested=None
        rr=parse_range(requested,total)
        if rr=="invalid":
            return self.sendb(b'',ct,416,{'Content-Range':f'bytes */{total}'})
        if rr:
            a,b=rr;n=b-a+1
            self.send_response(206);self.send_header("Content-Type",ct);self.send_header("Accept-Ranges","bytes")
            self.send_header("Content-Range",f"bytes {a}-{b}/{total}");self.send_header("Content-Length",str(n))
            self.send_header("X-IZZI-Replay","complete-media-range")
            self.send_header("ETag",etag);self.send_header("Cache-Control","private, max-age=0, must-revalidate");self.end_headers()
            if self.command!="HEAD":
                with f.open("rb") as x:
                    x.seek(a);self.stream_file(x,n)
            return
        self.send_response(200);self.send_header("Content-Type",ct);self.send_header("Accept-Ranges","bytes")
        self.send_header("Content-Length",str(total));self.send_header("X-IZZI-Replay","complete-media")
        self.send_header("ETag",etag);self.send_header("Cache-Control","private, max-age=0, must-revalidate");self.end_headers()
        if self.command!="HEAD":
            with f.open("rb") as stream:self.stream_file(stream,total)

    def stream_file(self,stream,remaining):
        while remaining:
            chunk=stream.read(min(1048576,remaining))
            if not chunk:break
            self.wfile.write(chunk);remaining-=len(chunk)

    def archive(self,m,host,path,q):
        import school_test_data
        if host in school_test_data.HOSTS and re.fullmatch(r'/api/tests/submit/\d+/?',path):
            return self.sendb(b'Online grading is not available offline','text/plain',501)
        if school_test_data.test_number('https://'+host+path) is not None:
            params=parse_qs(q);callbacks=params.get('testrequest',[])
            if callbacks and (len(callbacks)!=1 or not re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$]{0,127}',callbacks[0])):
                return self.sendb(b'Invalid JSONP callback','text/plain',400)
            data=school_test_data.archived('https://'+host+path,m,ARCHIVE_DIR)
            if data:
                encoded=json.dumps(data,ensure_ascii=True)
                if callbacks:return self.sendb((callbacks[0]+'('+encoded+');').encode(),'application/javascript')
                return self.sendb(encoded.encode(),'application/json')
            return self.sendb(b'Archived test questions are unavailable','text/plain',404)
        if _izzi_host(host) and path.startswith('/__offline_capture__/'):
            return self.sendb(b'{"capture":false,"available":false}','application/json')
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
        if not r:
            font=bundled_assets.asset(host,path)
            if font:return self.sendfile(font,replay_mime(path,'audio/wav' if ext=='.wav' else ''))
            runtime=geogebra_runtime.asset(host,path)
            if runtime:
                ct=replay_mime(path,mimetypes.guess_type(path)[0] or 'application/octet-stream')
                if ct.startswith('text/') or ct in TEXT:
                    encoding='gzip' if self.gzip_text(ct) else 'identity'
                    def prepare_runtime():
                        data=runtime.read_bytes()
                        return gzip.compress(data,compresslevel=3,mtime=0) if encoding=='gzip' else data
                    data,etag=replay_cache.prepared(runtime,('geogebra',encoding),prepare_runtime)
                    return self.send_cached(data,ct,etag=etag,encoding=encoding)
                return self.sendfile(runtime,ct)
        # Retain real upstream errors when there is no usable body alternative.
        if not r and usable:
            error=find(m,host,path,q,None,book)
            if error and 300<=error.get('status',0)<400 and error.get('location'):
                from urllib.parse import urljoin
                import external_links
                target=urlparse(urljoin('https://'+host+path,error['location']))
                if external_links.valid_url(target.geturl()):
                    local=(target.path if target.hostname==SOURCE_HOST else '/__host__/'+target.netloc+target.path)+('?' + target.query if target.query else '')+('#'+target.fragment if target.fragment else '')
                    return self.sendb(b'', 'text/plain',error['status'],extra={'Location':local})
            if error and error.get('status')==206 and not complete_body(error) and ext in MEDIA_EXT:
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
            if r.get("status")==206 and not complete_body(r,f.stat().st_size):
                print("[MEDIA INCOMPLETE]",path,r.get("content_range"))
                return self.sendb(b"Incomplete captured media range","text/plain; charset=utf-8",409)
            if ext==".mp4" and not mime.startswith("video/"):
                ct="video/mp4"
            print("[MEDIA REPLAY]","complete="+str(bool(r.get("complete"))),
                  "range="+str(self.headers.get("Range")),r["key"],path)
            return self.sendfile(f,ct)
        if (ext in FONT_EXT or mime.startswith(('image/','font/'))) and mime!='image/svg+xml':return self.sendfile(f,ct)
        static=not path.startswith('/api/') and (ext in {'.js','.css','.svg'} or mime=='image/svg+xml' or (ext=='.json' and '/datastore/blocks/' in path))
        if static:
            import external_links
            try:
                encoding='gzip' if f.stat().st_size>=1024 and self.gzip_text(ct) else 'identity'
                def prepare():
                    data=rewrite(f.read_bytes(),host,html_document=False)
                    return gzip.compress(data,compresslevel=3,mtime=0) if encoding=='gzip' else data
                data,etag=replay_cache.prepared(f,(host,external_links.hosts(),encoding),prepare)
                return self.send_cached(data,ct,etag=etag,encoding=encoding)
            except UnicodeDecodeError:
                return self.sendb(b'Captured static resource is compressed/corrupt. Recapture it.','text/plain; charset=utf-8',502)
        b=f.read_bytes()
        if ext in DOC_EXT or '/files/' in path:
            sender=self.sendb if path.startswith('/api/') else self.send_cached
            return sender(b,ct,extra={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(Path(unquote(path)).name,safe='')})
        if mime.startswith("text/") or mime in TEXT or "javascript" in mime:
            try:
                if mime.startswith('text/html'):
                    import geogebra_capture
                    b=geogebra_capture.prepare_html(b,'https://'+host+path)
                b=rewrite(b,host,html_document=mime.startswith('text/html'))
                if path.lower().endswith(".html"): b=inject_media_map(b,path)
            except UnicodeDecodeError:
                print("[BAD TEXT BLOB]",r["key"],path)
                return self.sendb(b"Captured text resource is still compressed/corrupt. Recapture with v3.2 and Disable Cache.","text/plain; charset=utf-8",502)
        return self.sendb(b,ct)

    def route(self):
        p=urlparse(self.path)
        if p.path.startswith('/__admin__'):return self.admin_page()
        if p.path in ('/__maintenance__','/__maintenance__/status'):
            if not self.admin_allowed():return self.sendb(b'Administrator required','text/plain',403)
            if p.path.endswith('/status'):
                data={'update':project_maintenance.updates.snapshot(),'managed':os.environ.get('IZZI_MANAGED_LAUNCH')=='1','windows':os.name=='nt','startup':project_maintenance.startup_status(STATE_DIR)}
                return self.sendb(json.dumps(data).encode(),'application/json')
            return self.maintenance_page()
        readonly=not self.admin_allowed()
        if readonly and (p.path in ('/__missing__','/__journal__','/__help__','/__operations__','/__cleanup__','/__videos__') or p.path.startswith(('/__ops__/','/__catalog__/','/__delete_book__/','/__videos__/')) or (p.path.startswith('/__book__/') and 'edit' in parse_qs(p.query))):
            return self.sendb(b'Administrator required','text/plain; charset=utf-8',403)
        if p.path in ('/__ui__/app.css','/__ui__/app.js','/__ui__/operations.js','/__ui__/videos.js','/__ui__/izzi-logo.svg'):
            filename=p.path.rsplit('/',1)[1]
            return self.send_cached((webui.ASSETS/filename).read_bytes(),'image/svg+xml' if filename.endswith('.svg') else 'text/css; charset=utf-8' if filename.endswith('.css') else 'application/javascript; charset=utf-8')
        if p.path=='/__videos__':return self.videos_page()
        if p.path=='/__videos__/status':
            import video_resume
            try:data={'report':video_resume.inspect(),'job':video_resume.jobs.snapshot()}
            except (OSError,ValueError) as error:return self.sendb(json.dumps({'error':str(error)},ensure_ascii=False).encode(),'application/json',503)
            return self.sendb(json.dumps(data,ensure_ascii=False).encode(),'application/json')
        if p.path=='/__ops__/status':
            if not self.admin_allowed():return self.sendb(b'{"error":"Admin login required"}','application/json',403)
            return self.sendb(json.dumps(operations.tasks.snapshot(),ensure_ascii=False).encode(),'application/json')
        if p.path=='/__operations__':
            content='<h1>Capture и проверки</h1><p><a href="/__videos__">Провери и довърши недовършени видеа</a></p>'
            if not self.admin_allowed():
                content+='<p class="empty">Управлението е достъпно само на компютъра със сървъра през http://127.0.0.1:8765/.</p>'
            else:
                content+='<p>Firefox proxy: адресът на компютъра със сървъра и порт 8877 (127.0.0.1:8877 при локален браузър). Login, сертификатът и Disable Cache се настройват в браузъра. При активен capture отчетите показват текущия момент; окончателните проверки пусни след обхода.</p><div id="operations" data-token="%s"><p id="operation-message" role="status"></p>'%html.escape(operations.tasks.token,quote=True)
                for task,title in [('capture','Capture proxy'),('checks','Всички проверки')]:
                    content+='<section class="task-panel"><h2>%s</h2><p id="%s-state" role="status">Зареждане…</p><button data-task="%s" data-action="start" disabled>Стартирай</button> <button data-task="%s" data-action="stop" disabled>Спри</button><pre id="%s-log" class="task-log" aria-label="Лог %s"></pre></section>'%(title,task,task,task,task,title)
                content+='</div><script src="/__ui__/operations.js" defer></script>'
            return self.sendb(self.ui(content,'Управление','operations').encode(),'text/html; charset=utf-8')
        if p.path=='/__help__':
            content='<h1>Как да използвам библиотеката</h1><h2>1. Запиши съдържание</h2><p>На компютъра с архива стартирай capture_mode.bat. Настрой Firefox proxy към 127.0.0.1:8877 и отвори оригиналния учебник с нормален login. Включи Disable Cache. Използвай обновения bookmarklet за избрания срок или раздел.</p><h2>2. Провери и подреди</h2><p>Изпълни run_all_checks.bat. Отвори учебника в библиотеката и избери „Подреди / преименувай / скрий“ за локални настройки.</p><h2>3. Възстанови ресурси</h2><p>От „Липсващи ресурси“ използвай „Изтегли“ или „Изтегли всички“ при интернет и активен capture proxy. След края презареди списъка.</p><h2>Достъп от локалната мрежа</h2><p>От друго устройство отвори http://&lt;IPv4 на компютъра&gt;:8765/. Firewall трябва да допуска порт 8765 в Private мрежата. За управление от LAN използвай „Администраторски вход“. Началният профил е admin с парола izzi. Данните се сменят от меню „Администратор“. Без вход библиотеката е достъпна за четене.</p><h2>Обновяване</h2><p>Спри capture и сървъра, запази резервно копие на archive/state и пусни update_project.bat. Стартирай сървъра отново. При нов bookmarklet обнови и адреса на Firefox bookmark.</p>'
            return self.sendb(self.ui(content,'Помощ','help').encode(),'text/html; charset=utf-8')
        if p.path=='/__cleanup__':return self.cleanup_page(p)
        try:
            m=load_archive_state(URL_MAP_FILE,{});books=load_archive_state(BOOKS_FILE,{})
            if not isinstance(m,Mapping) or not isinstance(books,Mapping):raise ValueError('invalid state root')
        except (OSError,ValueError) as error:
            print('[STATE ERROR]',type(error).__name__)
            return self.sendb(b'Archive state unavailable. Stop capture and run checks/lesson_diagnostic.bat.','text/plain; charset=utf-8',503)
        if p.path.startswith('/__delete_book__/'):
            import delete_book
            bid=p.path.rsplit('/',1)[-1]
            try:result=delete_book.plan(bid,STATE_DIR,ARCHIVE_DIR)
            except (ValueError,OSError):return self.sendb(b'Deletion preview unavailable','text/plain',400)
            content='<h1>Изтриване на учебник</h1><p><b>%s</b></p><p>Ще се премахнат учебникът, настройките му, локалният му журнал и %d отделни файла (%.1f MB). Споделените и неразпознатите общи ресурси се запазват. Изтриването не може да се отмени. Спри capture преди потвърждението.</p><form method="post"><input type="hidden" name="token" value="%s"><button>Изтрий учебника и съдържанието</button></form><p><a href="/__book__/%s">Отказ</a></p>'%(html.escape(result['title']),len(result['files']),result['bytes']/1048576,html.escape(operations.tasks.token,quote=True),html.escape(bid))
            return self.sendb(self.ui(content,'Изтриване').encode(),'text/html; charset=utf-8')
        if p.path=="/":
            covers=book_covers.catalog_covers(m,ARCHIVE_DIR,books)
            stages={**{str(grade)+'. клас':[] for grade in range(1,13)},'Без определен клас':[]}
            items=[]
            for bid,b in sorted(books.items(),key=lambda item:(covers[item[0]]['grade'] or 99,item[1].get('title',''),item[0])):
                card=webui.book_card(bid,b.get('title','Учебник '+bid),covers[bid]['src'],covers[bid]['decoration'],covers[bid]['palette'])
                grade=covers[bid]['grade']
                stage=str(grade)+'. клас' if 1<=grade<=12 else 'Без определен клас'
                stages[stage].append(card);items.append(card)
            page=''.join('<section class="book-stage"><h2>'+stage+'</h2><ul class="book-grid">'+''.join(cards)+'</ul></section>' for stage,cards in stages.items() if cards)
            if not items:
                page+='<section class="empty"><h2>Библиотеката е празна</h2>'+('<p>Все още няма добавени учебници.</p>' if readonly else '<p>Запиши първия си урок чрез capture или импортирай HAR файл. Тук ще се появят учебниците от твоя архив.</p><a href="/__help__">Как да започна →</a>')+'</section>'
            return self.sendb(self.ui(page,search=bool(items),catalog=True,readonly=readonly).encode(),"text/html; charset=utf-8")
        if p.path.startswith("/__book__/"):
            bid=p.path.split("/")[-1];b=books.get(bid)
            if not b:return self.sendb(b"Unknown book","text/plain",404)
            try:
                preferences=load_archive_state(STATE_DIR/'library_catalog.json',{})
                session=load_archive_state(STATE_DIR/'capture_session.json',{'visits':[]})
                ls=library_catalog.ordered_lessons(bid,b,session,preferences)
            except (OSError,ValueError,TypeError,AttributeError):
                return self.sendb(b'Library settings unavailable','text/plain',503)
            if parse_qs(p.query).get('edit')==['1']:
                automatic=parse_qs(p.query).get('auto')==['1']
                if automatic:
                    import catalog_restore
                    ls=catalog_restore.restore(bid,ls,m,ARCHIVE_DIR)
                rows=[]
                for index,x in enumerate(ls,1):
                    lid=html.escape(x['id'],quote=True)
                    rows.append('<tr><td>%s</td><td><input type="number" name="order_%s" value="%d" required></td><td><input name="name_%s" value="%s" maxlength="300"></td><td><input name="module_%s" value="%s" maxlength="300"></td><td><input name="number_%s" value="%s" maxlength="40"></td><td><input type="checkbox" name="hidden_%s" %s></td></tr>'%(lid,lid,index,lid,html.escape(x['title'],quote=True),lid,html.escape(x.get('module',''),quote=True),lid,html.escape(x.get('original_number',''),quote=True),lid,'checked' if x['hidden'] else ''))
                page='<!doctype html><meta charset="utf-8"><h1>Подреждане на уроци</h1><p>По-малкият номер се показва по-рано. Скриването запазва архивираните файлове и директните адреси на уроците.</p><form method="post" action="/__catalog__/%s"><table><tr><th>ID</th><th>Ред</th><th>Име</th><th>Раздел</th><th>Оригинален номер</th><th>Скрит</th></tr>%s</table><button>Запази</button></form><p><a href="/__book__/%s">Назад</a></p>'%(html.escape(bid),''.join(rows),html.escape(bid))
                notice='<p>Автоматично предложение от архива. Провери полетата и натисни „Запази“. Ако няма данни за раздел, попълни го ръчно.</p>' if automatic else '<p><a class="download" href="?edit=1&amp;auto=1">Предложи имена и раздели от архива</a></p>'
                page=page.replace('<form ',notice+'<form ',1)
                page=page.replace('<table>', '<input type="hidden" name="token" value="'+html.escape(operations.tasks.token,quote=True)+'"><table>',1)
                page=page.replace('<table>','<div class="table-wrap"><table>').replace('</table>','</table></div>')
                return self.sendb(self.ui(page,'Подреждане').encode(),'text/html; charset=utf-8')
            groups={}
            for x in ls:
                if not x['hidden']:groups.setdefault(x.get('module') or '',[]).append(x)
            sections=[]
            for module,lessons in groups.items():
                items=''.join('<li data-search-item data-search-text="%s"%s><a href="%s">%s</a> <small>(%s)</small></li>'%(html.escape(module,quote=True),' class="original-number"' if x.get('original_number') else '',html.escape(x['path']),html.escape(x['title']),html.escape(x['id'])) for x in lessons)
                heading=module or ('Уроци без записан раздел' if any(groups) else 'Уроци')
                sections.append('<section class="lesson-section"><h2>%s</h2><ol class="lesson-list">%s</ol></section>'%(html.escape(heading),items))
            items=''.join(sections)
            known,available=page_counts(m,bid,b)
            edit_link='' if readonly else ' · <a class="download" href="?edit=1">Подреди / преименувай / скрий</a> · <a class="download" href="/__delete_book__/'+html.escape(bid)+'">Изтрий учебника</a>'
            content='<h1>%s</h1><p>ID %s · %d известни страници · %d с наличен HTML</p><p><a href="/">← Библиотека</a>%s</p>%s'%(html.escape(b["title"]),html.escape(bid),known,available,edit_link,items)
            if not items:content+='<p class="empty">Няма показани уроци. Провери скритите страници в редактора.</p>'
            return self.sendb(self.ui(content,'Уроци',search=bool(items),readonly=readonly).encode(),"text/html; charset=utf-8")
        if p.path=="/__offline__/gtag.js":
            return self.sendb(b"window.dataLayer=window.dataLayer||[];window.gtag=window.gtag||function(){window.dataLayer.push(arguments);};","application/javascript")
        if p.path=="/__offline__/youtube-api.js":
            return self.sendb(b'/* YouTube player API is unavailable in offline replay. */',"application/javascript")
        if p.path=="/__offline__/asset-status":
            target=urlparse(parse_qs(p.query).get('url',[''])[0])
            if target.scheme not in ('http','https') or not _izzi_host(target.hostname) or target.username or target.password:
                return self.sendb(b'{"available":false}',"application/json",400)
            ext=Path(target.path).suffix.lower()
            record=find(m,target.hostname,target.path,target.query,lambda r:usable_body(r,ARCHIVE_DIR,ext))
            return self.sendb(json.dumps({'available':bool(record or bundled_assets.asset(target.hostname,target.path) or geogebra_runtime.asset(target.hostname,target.path))}).encode(),'application/json')
        if p.path=='/__journal__':
            summary=progress_journal.summarize(PROGRESS_DIR)
            content='<h1>Локален журнал</h1><p>Записани заявки: %d · Невалидни редове: %d</p><p>Журналът пази локални заявки; това не е възстановен прогрес от оригиналния сървър. Тук се показват само броячи.</p>'%(summary['records'],summary['invalid_lines'])
            for book in summary['books']:
                content+='<h2>Учебник %s</h2><div class="table-wrap"><table><tr><th>Заявка</th><th>Брой</th></tr>'%html.escape(str(book['book']))
                for endpoint,count in book['endpoints'].items():content+='<tr><td>%s</td><td>%d</td></tr>'%(html.escape(endpoint),count)
                content+='</table></div>'
            if not summary['books']:content+='<p class="empty">Все още няма локални записи.</p>'
            return self.sendb(self.ui(content,'Журнал','journal').encode(),'text/html; charset=utf-8')
        if p.path=="/__offline__/progress":
            return self.sendb(json.dumps(progress_journal.summarize(PROGRESS_DIR),ensure_ascii=False).encode(),"application/json")
        if p.path.startswith('/__offline__/youtube-video/'):
            import youtube_download
            identifier=p.path.rsplit('/',1)[-1];video=youtube_download.local_file(identifier)
            if not video:return self.sendb(b'Video not downloaded','text/plain',404)
            return self.sendfile(video,'video/mp4' if video.suffix=='.mp4' else 'video/webm')
        if p.path.startswith("/__offline__/external-media/"):
            import youtube_download
            identifier=p.path.rsplit('/',1)[-1]
            if youtube_download.local_file(identifier):
                times=[]
                for key in ('start','end'):
                    value=parse_qs(p.query).get(key,[''])[0]
                    times.append(value if re.fullmatch(r'\d+(?:\.\d+)?',value) else '')
                fragment=('#t='+times[0]+(','+times[1] if times[1] else '')) if any(times) else ''
                return self.sendb(('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;background:#000}video{width:100%;height:100vh}</style><video controls playsinline preload="metadata" src="/__offline__/youtube-video/'+identifier+fragment+'"></video>').encode(),'text/html; charset=utf-8')
            return self.sendb('<!doctype html><meta charset="utf-8"><p>Външното видео не е включено в офлайн архива.</p>'.encode(),"text/html; charset=utf-8")
        if p.path=="/__missing__":
            events=[];seen=set();f=missing_log()
            if f.exists():
                with f.open(encoding="utf-8") as stream:
                    for line in stream:
                        try:e=json.loads(line)
                        except:continue
                        k=(e.get("host"),e.get("path"),e.get("query"))
                        if k not in seen:seen.add(k);events.append(e)
            missing,warnings,resolved=current_missing(events,m)
            def rows(items):
                rendered=[]
                marker=str(time.time_ns())
                for label,url in items:
                    original=urlparse('https://'+url)
                    action=''
                    if _izzi_host(original.hostname) and not original.username and not original.password:
                        target='https://'+url+'?__izzi_offline_recover='+marker
                        action=' <a class="download" href="%s" target="_blank" rel="noopener noreferrer">Изтегли</a>'%html.escape(target,quote=True)
                    rendered.append('<li data-search-item>%s <code>%s</code>%s</li>'%(label,html.escape(url),action))
                return ''.join(rendered)
            page='<!doctype html><meta charset="utf-8"><h1>Текущи липсващи ресурси (%d)</h1><p>Възстановени от историческия лог: %d. Логът е запазен.</p><ul>%s</ul><h2>Предупреждения (%d)</h2><ul>%s</ul>'%(len(missing),resolved,rows(missing),len(warnings),rows(warnings))
            page=page.replace('<h1>', '<style>.download{display:inline-block;padding:5px 10px;margin:4px;border:1px solid #567;border-radius:4px;text-decoration:none}li{margin:8px 0;overflow-wrap:anywhere}</style><p><a href="/">← Библиотека</a></p><p>„Изтегли“ отваря оригиналния ресурс в нов таб. За запис в архива използвай интернет и Firefox с включен capture proxy и Disable Cache. След зареждане се върни тук и презареди списъка. При достъп през LAN записването трябва да минава през capture proxy на компютъра с библиотеката. Origin 404 може да остане недостъпен.</p><h1>',1)
            page+='<p><button id="download-all">Изтегли всички</button> <button id="download-stop" disabled>Спри</button></p><p id="download-status" role="status">Изтеглянето включва ресурсите от списъка и предупрежденията. Origin 404 може да остане недостъпен.</p>'
            page+='<script>'+Path(__file__).with_name('missing_download.js').read_text(encoding='utf-8')+'</script>'
            page=re.sub(r'<style>.*?</style>','',page,flags=re.S).replace('<ul>','<ul class="resource-list">')
            return self.sendb(self.ui(page,'Липсващи ресурси','missing',search=bool(missing or warnings)).encode(),"text/html; charset=utf-8")
        if p.path.startswith('/__offline_capture__/'):
            # Capture probes belong to the proxy, never to the archived site.
            return self.sendb(b'{"capture":false,"available":false}','application/json')
        if p.path.startswith("/__host__/"):
            rest=p.path[len("/__host__/"):]
            if "/" not in rest:return self.sendb(b"Bad route","text/plain",400)
            host,tail=rest.split("/",1);return self.archive(m,unquote(host),"/"+tail,p.query)
        return self.archive(m,SOURCE_HOST,p.path,p.query)

    def do_GET(self):
        with archive_db.read_session():self.route()
    def do_HEAD(self):
        with archive_db.read_session():self.route()
    def progress(self):
        if urlparse(self.path).path.startswith(('/__admin__','/__maintenance__')):
            self.close_connection=True;return self.sendb(b'Method not allowed','text/plain',405,{'Allow':'GET, HEAD, POST'})
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
    def do_POST(self):
        if urlparse(self.path).path=='/__maintenance__/action':return self.maintenance_action()
        if urlparse(self.path).path.startswith('/__admin__'):return self.admin_action()
        if urlparse(self.path).path=='/__cleanup__':return self.cleanup_action()
        if urlparse(self.path).path.startswith('/__delete_book__/'):return self.delete_book_action()
        if urlparse(self.path).path in ('/__ops__/action','/__videos__/action'):return self.control_action()
        if urlparse(self.path).path.startswith('/__catalog__/'):
            return self.catalog_save()
        self.progress()

    def auth(self):
        return admin_account.manager(STATE_DIR)

    def admin_session(self):
        return self.auth().session(self.headers.get('Cookie',''),self.headers.get('Host',''))

    def admin_allowed(self):
        return self.control_local() or self.admin_session() is not None

    def origin_valid(self):
        origin=self.headers.get('Origin')
        if not origin:return True
        p=urlparse(origin)
        return p.scheme in ('http','https') and p.netloc.lower()==self.headers.get('Host','').lower() and not p.username and not p.password and not p.query and not p.fragment and p.path in ('','/')

    def ui(self,*args,**kwargs):
        kwargs.setdefault('readonly',not self.admin_allowed())
        kwargs['admin_session']=self.admin_session() is not None
        return webui.page(*args,**kwargs)

    def admin_cookie(self,name,value,age):
        import ssl
        return admin_account.cookie(name,value,age,isinstance(self.connection,ssl.SSLSocket))

    def admin_redirect(self,target,cookie=None):
        headers={'Location':target}
        if cookie:headers['Set-Cookie']=cookie
        return self.sendb(b'','text/plain',303,headers)

    def admin_form(self,purpose,message='',status=200):
        try:
            record=self.auth().record()
            nonce=self.auth().nonce(self.headers.get('Host',''),purpose)
        except (OSError,ValueError):return self.sendb('Настройката на профила е недостъпна. Провери state/admin_account.json или изпълни admin_account.py на сървъра.'.encode(),'text/plain; charset=utf-8',503)
        token='<input type="hidden" name="csrf" value="'+html.escape(nonce,quote=True)+'">'
        note='<p class="auth-message" role="status">'+html.escape(message)+'</p>' if message else ''
        if purpose=='login':
            content='<h1>Администраторски вход</h1>'+note
            if not record:content+='<p>Все още няма администраторски профил. Създай го от меню „Администратор“ на компютъра с библиотеката през http://127.0.0.1:8765/.</p>'
            else:content+='<form method="post" action="/__admin__/login" class="admin-form">'+token+'<label>Потребителско име<input name="username" autocomplete="username" maxlength="64" required></label><label>Парола<input name="password" type="password" autocomplete="current-password" maxlength="1024" required></label><button>Вход</button></form><p>Сесията е валидна до 8 часа. След работа използвай „Изход“.</p>'
        elif purpose=='account':
            username=html.escape(record['username'] if record else 'admin',quote=True)
            content='<h1>Администраторски профил</h1>'+note+'<p>Този профил дава достъп до управлението на библиотеката през локалната мрежа. Локалното управление през 127.0.0.1 остава без вход.</p><form method="post" action="/__admin__/account" class="admin-form">'+token+'<label>Потребителско име<input name="username" value="'+username+'" autocomplete="username" minlength="3" maxlength="64" required></label>'
            if not self.control_local():content+='<label>Текуща парола<input name="current_password" type="password" autocomplete="current-password" maxlength="1024" required></label>'
            content+='<label>Нова парола — поне 4 знака<input name="password" type="password" autocomplete="new-password" minlength="4" maxlength="1024" required></label><label>Повтори новата парола<input name="confirm" type="password" autocomplete="new-password" minlength="4" maxlength="1024" required></label><button>Запази профила</button></form><p>Запазването прекратява всички предишни администраторски сесии. При забравена парола я смени от този екран на компютъра с библиотеката.</p>'
        else:
            content='<h1>Изход от управлението</h1><form method="post" action="/__admin__/logout" class="admin-form">'+token+'<p>Библиотеката ще остане достъпна за четене.</p><button>Изход</button></form>'
        content+='<p><a href="/">← Библиотека</a></p>'
        headers={'Set-Cookie':self.admin_cookie(admin_account.NONCE_COOKIE,nonce,admin_account.NONCE_TTL),'X-Frame-Options':'DENY','Content-Security-Policy':"frame-ancestors 'none'; form-action 'self'",'Referrer-Policy':'same-origin'}
        return self.sendb(self.ui(content,'Администратор','admin').encode(),'text/html; charset=utf-8',status,headers)

    def admin_page(self):
        p=urlparse(self.path)
        if p.path in ('/__admin__','/__admin__/'):return self.admin_redirect('/__admin__/account' if self.admin_allowed() else '/__admin__/login')
        if p.path=='/__admin__/login':return self.admin_form('login','Паролата е сменена. Влез с новите данни.' if 'changed' in parse_qs(p.query) else '')
        if p.path=='/__admin__/account':
            if not self.admin_allowed():return self.admin_redirect('/__admin__/login')
            return self.admin_form('account','Профилът е запазен. Предишните сесии са прекратени.' if 'saved' in parse_qs(p.query) else '')
        if p.path=='/__admin__/logout':return self.admin_form('logout')
        return self.sendb(b'Not found','text/plain',404)

    def admin_action(self):
        purpose={'/__admin__/login':'login','/__admin__/account':'account','/__admin__/logout':'logout'}.get(urlparse(self.path).path)
        if not purpose:return self.sendb(b'Not found','text/plain',404)
        if not self.origin_valid() or not self.auth().valid_authority(self.headers.get('Host','')):
            self.close_connection=True;return self.sendb(b'Forbidden origin','text/plain',403)
        if purpose=='account' and not self.admin_allowed():
            self.close_connection=True;return self.sendb(b'Administrator required','text/plain',403)
        try:
            if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type','').split(';')[0]!='application/x-www-form-urlencoded':raise ValueError('Invalid form')
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=8192:raise ValueError('Invalid length')
            self.connection.settimeout(10);raw=self.rfile.read(length)
            if len(raw)!=length:raise ValueError('Incomplete form')
            form=parse_qs(raw.decode('utf8'),keep_blank_values=True,max_num_fields=12)
            value=lambda key:form.get(key,[''])[0]
            if not self.auth().consume_nonce(self.headers.get('Cookie',''),value('csrf'),self.headers.get('Host',''),purpose):
                return self.sendb(b'Invalid confirmation. Reload the form.','text/plain',403)
            if purpose=='logout':
                self.auth().logout(self.headers.get('Cookie',''))
                return self.admin_redirect('/',self.admin_cookie(admin_account.COOKIE,'',0))
            if purpose=='account':
                if value('password')!=value('confirm'):raise ValueError('Двете пароли не съвпадат.')
                self.auth().set_account(value('username'),value('password'),local=self.control_local(),current_password=value('current_password'))
                return self.admin_redirect('/__admin__/account?saved=1' if self.control_local() else '/__admin__/login?changed=1',self.admin_cookie(admin_account.COOKIE,'',0))
            token=self.auth().login(value('username'),value('password'),self.client_address[0],self.headers.get('Host',''))
            if not token:return self.admin_form('login','Неправилно потребителско име или парола.',401)
            return self.admin_redirect('/',self.admin_cookie(admin_account.COOKIE,token,admin_account.SESSION_TTL))
        except admin_account.LoginThrottled:
            self.close_connection=True
            return self.sendb('Твърде много опити за вход. Опитай след 5 минути.'.encode(),'text/plain; charset=utf-8',429,{'Retry-After':'300'})
        except (UnicodeError,ValueError) as error:
            self.close_connection=True
            return self.admin_form(purpose,str(error),400)
        except (OSError,TimeoutError):
            self.close_connection=True;return self.sendb(b'Administrator account unavailable','text/plain',503)

    def control_local(self):
        # Check the socket peer AND Host; forwarded headers are never trusted.
        host=urlparse('http://'+self.headers.get('Host','')).hostname
        return self.client_address[0] in ('127.0.0.1','::1') and host in ('127.0.0.1','localhost','::1')

    def maintenance_page(self):
        content='<h1>Поддръжка на проекта</h1><div id="maintenance" data-token="'+html.escape(operations.tasks.token,quote=True)+'"><section id="update"><h2>Обновяване от GitHub</h2><p>Изтегля последните промени за текущия клон main или WebUI. Спри capture, проверките и изтеглянето на видеа. Локални промени и промени на зависимости блокират обновяването.</p><button data-maintenance="update">Провери и обнови от GitHub</button> <button data-maintenance="restart" disabled>Рестартирай библиотеката</button><p id="update-state" role="status"></p><pre id="update-log" class="task-log"></pre></section><section id="startup"><h2>Стартиране с Windows</h2>'
        if os.name=='nt' and self.control_local():
            content+='<p>Създава задача преди входа в Windows под текущия потребител на сървъра. Ще се отворят UAC и системен прозорец за Windows паролата (не PIN). Задачата стартира библиотеката и capture 30 секунди след зареждане на Windows.</p><button data-maintenance="startup">Създай / обнови Windows задача</button>'
        elif os.name=='nt':content+='<p>За създаване на задачата отвори тази страница на Windows компютъра през http://127.0.0.1:8765/.</p>'
        else:content+='<p>Task Scheduler е наличен само на Windows. Docker контейнерът използва restart: unless-stopped.</p>'
        content+='<p id="startup-state" role="status"></p></section><p id="maintenance-message" role="status"></p></div><script src="/__ui__/maintenance.js" defer></script>'
        return self.sendb(self.ui(content,'Поддръжка','maintenance').encode(),'text/html; charset=utf-8')

    def maintenance_action(self):
        global RESTART_REQUESTED
        if not self.admin_allowed() or not self.origin_valid() or self.headers.get('X-IZZI-Control')!=operations.tasks.token:
            self.close_connection=True;return self.sendb(b'Administrator confirmation required','text/plain',403)
        try:
            if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('Invalid request')
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=256:raise ValueError('Invalid request length')
            self.connection.settimeout(10);raw=self.rfile.read(length)
            if len(raw)!=length:raise ValueError('Incomplete request')
            data=json.loads(raw)
            if not isinstance(data,dict) or set(data)!={'action'}:raise ValueError('Unknown command')
            action=data['action']
            if action=='update':project_maintenance.updates.start();result={'message':'Проверката и обновяването са стартирани.'}
            elif action=='startup':
                if not self.control_local():return self.sendb(b'Local Windows control required','text/plain',403)
                result=project_maintenance.launch_startup_setup()
            elif action=='restart':
                if os.environ.get('IZZI_MANAGED_LAUNCH')!='1' or RUNNING_SERVER is None:raise ValueError('Стартирай проекта чрез start_library.bat / project_launcher.py, или рестартирай ръчно.')
                if project_maintenance.updates.snapshot()['state']=='running':raise ValueError('Изчакай обновяването да приключи.')
                project_maintenance.require_idle();RESTART_REQUESTED=True
                threading.Timer(1,RUNNING_SERVER.shutdown).start();result={'message':'Библиотеката се рестартира. Страницата ще се свърже отново.'}
            else:raise ValueError('Unknown command')
            return self.sendb(json.dumps(result,ensure_ascii=False).encode(),'application/json')
        except (OSError,ValueError,TimeoutError) as error:
            self.close_connection=True
            return self.sendb(json.dumps({'error':str(error)},ensure_ascii=False).encode(),'application/json',400)

    def control_action(self):
        origin=self.headers.get('Origin')
        if not self.admin_allowed() or not self.origin_valid() or self.headers.get('X-IZZI-Control')!=operations.tasks.token:
            self.close_connection=True
            return self.sendb(b'{"error":"Local control required"}','application/json',403)
        try:
            if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type')!='application/json':raise ValueError('Invalid request')
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=2048:raise ValueError('Invalid length')
            self.connection.settimeout(10)
            raw=self.rfile.read(length)
            if len(raw)!=length:raise ValueError('Incomplete request')
            data=json.loads(raw)
            if isinstance(data,dict) and data.get('action')=='start' and project_maintenance.updates.snapshot()['state']=='running':raise ValueError('Изчакай обновяването да приключи.')
            if urlparse(self.path).path=='/__videos__/action':
                import video_resume
                if not isinstance(data,dict) or data.get('action') not in ('start','stop') or not isinstance(data.get('id','all'),str):raise ValueError('Unknown command')
                if data['action']=='start':video_resume.jobs.start(data.get('id','all'))
                else:video_resume.jobs.stop()
                return self.sendb(b'{"ok":true}','application/json')
            if not isinstance(data,dict) or data.get('task') not in ('capture','checks') or data.get('action') not in ('start','stop'):raise ValueError('Unknown command')
            if data['action']=='start':operations.tasks.start(data['task'])
            else:operations.tasks.stop(data['task'])
        except (ValueError,OSError,TimeoutError) as error:
            self.close_connection=True
            return self.sendb(json.dumps({'error':str(error)},ensure_ascii=False).encode(),'application/json',400)
        return self.sendb(b'{"ok":true}','application/json')

    def videos_page(self):
        content='<h1>Недовършени видеа</h1><p>Проверка на наличните MP4 файлове и видео части. За довършване са нужни интернет и работещ capture proxy. Изтеглят се липсващите диапазони; наличните части се запазват.</p><p>При отказ за достъп отвори видеото в оригиналния урок с правилния профил във Firefox през capture proxy и опитай отново. Cookies и tokens се използват само в паметта на proxy и не се записват на диска. YouTube видеата се изтеглят чрез отделния YouTube механизъм.</p>'
        content+='<div id="video-resume" data-token="%s"><p id="video-message" role="status"></p><button id="videos-refresh">Провери отново</button> <button data-video="all" %s>Довърши всички</button> <button id="videos-stop" disabled>Спри изтеглянето</button><p id="videos-state" role="status">Проверка на архива…</p><div id="videos-list"></div><pre id="videos-log" class="task-log"></pre></div><script src="/__ui__/videos.js" defer></script>'%(html.escape(operations.tasks.token,quote=True),'disabled')
        return self.sendb(self.ui(content,'Недовършени видеа','videos').encode(),'text/html; charset=utf-8')

    def cleanup_page(self,p):
        import archive_cleanup
        query=parse_qs(p.query);include=query.get('incomplete')==['1']
        content='<h1>Почистване на архива</h1><p>Първо прегледай отчета. Файловете се преместват в state/cleanup_trash за възстановяване. Място на диска се освобождава след отделно окончателно изтриване.</p><p><a href="/__videos__">Провери и довърши недовършените видеа</a>, преди да премахваш видео части.</p>'
        token='<input type="hidden" name="token" value="'+html.escape(operations.tasks.token,quote=True)+'">'
        try:
            if query.get('purge'):
                batch=query['purge'][0];result=archive_cleanup.trash_report(STATE_DIR,batch)
                content+='<h2>Окончателно изтриване</h2><p>%d файла · %.1f MB. Това действие не може да се отмени.</p><form method="post">%s<input type="hidden" name="action" value="purge"><input type="hidden" name="batch" value="%s"><input type="hidden" name="review" value="%s"><button>Потвърди окончателното изтриване</button></form><p><a href="/__cleanup__">Отказ</a></p>'%(result['count'],result['bytes']/1048576,token,batch,result['fingerprint'])
            else:
                result=archive_cleanup.report(ARCHIVE_DIR,STATE_DIR,include)
                if query.get('format')==['json']:return self.sendb(json.dumps(result,ensure_ascii=False,indent=2).encode(),'application/json',extra={'Content-Disposition':'attachment; filename="cleanup-report.json"'})
                content+='<form class="cleanup-options" method="get"><label><input type="checkbox" name="incomplete" value="1" %s> Включи недовършените видео части (ще се загуби натрупаното изтегляне)</label><button>Генерирай отчет</button></form>'%('checked' if include else '')
                content+='<h2>Предварителен отчет</h2><p>%d файла за преместване · %.1f MB. Запазени файлове и недовършени части: %d.</p><p><a href="?format=json%s">Изтегли пълния отчет</a></p>'%(len(result['files']),result['bytes']/1048576,len(result['preserved']),'&amp;incomplete=1' if include else '')
                content+='<div class="table-wrap"><table><tr><th>Категория</th><th>Файл</th><th>Размер</th></tr>'+''.join('<tr><td>%s</td><td>%s/%s</td><td>%.1f KB</td></tr>'%(html.escape(e['category']),e['root'],html.escape(e['path']),e['size']/1024) for e in result['files'][:200])+'</table></div>'
                if len(result['files'])>200:content+='<p>Показани са първите 200 файла; пълният списък е в отчета.</p>'
                if result['files']:content+='<p>Спри capture и импорта на HAR преди почистване. Новите неизползвани файлове се запазват поне 5 минути.</p><form method="post">%s<input type="hidden" name="action" value="clean"><input type="hidden" name="review" value="%s"><input type="hidden" name="incomplete" value="%s"><button>Потвърди преместването</button></form>'%(token,result['fingerprint'],'1' if include else '0')
        except (OSError,ValueError,TypeError,AttributeError,KeyError) as error:
            content+='<p class="empty">Почистването е блокирано: '+html.escape(str(error))+'</p>'
        if not query.get('purge'):
            try:
                for batch in archive_cleanup.batches(STATE_DIR):
                    content+='<section><h2>Папка за възстановяване %s</h2><p>%d файла · %.1f MB</p><form method="post">%s<input type="hidden" name="action" value="restore"><input type="hidden" name="batch" value="%s"><button>Възстанови</button></form><p><a href="?purge=%s">Изтрий окончателно…</a></p></section>'%(batch['id'],batch['count'],batch['bytes']/1048576,token,batch['id'],batch['id'])
            except (OSError,ValueError):content+='<p>Папките за възстановяване не могат да се прочетат.</p>'
        return self.sendb(self.ui(content,'Почистване','cleanup').encode(),'text/html; charset=utf-8')

    def cleanup_action(self):
        if not self.admin_allowed() or not self.origin_valid():
            self.close_connection=True;return self.sendb(b'Administrator required','text/plain',403)
        try:
            if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type','').split(';')[0]!='application/x-www-form-urlencoded':raise ValueError('Invalid request')
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=2048:raise ValueError('Invalid length')
            self.connection.settimeout(10);raw=self.rfile.read(length)
            if len(raw)!=length:raise ValueError('Incomplete request')
            form=parse_qs(raw.decode('utf8'))
            if form.get('token')!=[operations.tasks.token]:return self.sendb(b'Invalid confirmation','text/plain',403)
            import archive_cleanup
            action=form.get('action',[''])[0]
            if action not in ('clean','restore','purge'):raise ValueError('Invalid action')
            if action!='purge' and operations.capture_port_busy():raise ValueError('Спри capture преди почистване или възстановяване.')
            if action=='clean':archive_cleanup.quarantine(ARCHIVE_DIR,STATE_DIR,form.get('review',[''])[0],form.get('incomplete')==['1'])
            elif action=='restore':archive_cleanup.restore(ARCHIVE_DIR,STATE_DIR,form.get('batch',[''])[0])
            else:archive_cleanup.purge(STATE_DIR,form.get('batch',[''])[0],form.get('review',[''])[0])
        except (OSError,ValueError,TypeError,AttributeError,KeyError) as error:return self.sendb(str(error).encode(),'text/plain; charset=utf-8',400)
        return self.sendb(b'','text/plain',303,extra={'Location':'/__cleanup__'})

    def delete_book_action(self):
        if not self.admin_allowed() or not self.origin_valid():
            self.close_connection=True;return self.sendb(b'Administrator required','text/plain',403)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if self.headers.get('Transfer-Encoding') or not 0<length<=2048:raise ValueError('Invalid request')
            self.connection.settimeout(10)
            form=parse_qs(self.rfile.read(length).decode('utf8'))
            if form.get('token')!=[operations.tasks.token]:return self.sendb(b'Invalid confirmation','text/plain',403)
            if operations.capture_port_busy():raise ValueError('Спри capture преди изтриване на учебника.')
            import delete_book
            delete_book.remove(urlparse(self.path).path.rsplit('/',1)[-1],STATE_DIR,ARCHIVE_DIR)
        except (ValueError,OSError) as error:
            return self.sendb(str(error).encode(),'text/plain; charset=utf-8',400)
        return self.sendb(b'','text/plain',303,extra={'Location':'/'})

    def catalog_save(self):
        if not self.admin_allowed():
            self.close_connection=True
            return self.sendb(b'Administrator required','text/plain',403)
        # Browser cross-origin writes must not modify the local catalogue.
        origin=self.headers.get('Origin')
        if not self.origin_valid():
            return self.sendb(b'Forbidden origin','text/plain',403)
        if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type','').split(';')[0]!='application/x-www-form-urlencoded':
            return self.sendb(b'Invalid form','text/plain',400)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=1024*1024:raise ValueError('invalid length')
            self.connection.settimeout(15)
            raw=self.rfile.read(length)
            if len(raw)!=length:raise ValueError('incomplete form')
            bid=urlparse(self.path).path.split('/')[-1]
            books=load_archive_state(BOOKS_FILE,{})
            if bid not in books:return self.sendb(b'Unknown book','text/plain',404)
            form=parse_qs(raw.decode('utf-8'),keep_blank_values=True)
            token=form.pop('token',None)
            if not self.control_local() and token!=[operations.tasks.token]:return self.sendb(b'Invalid confirmation','text/plain',403)
            library_catalog.update(STATE_DIR/'library_catalog.json',bid,books[bid].get('lessons',{}),form)
        except (ValueError,UnicodeError):
            return self.sendb(b'Invalid catalogue form','text/plain',400)
        except (OSError,TimeoutError):
            return self.sendb(b'Catalogue save failed','text/plain',500)
        return self.sendb(b'','text/plain',303,{'Location':'/__book__/'+quote(bid,safe='')})
    def do_PUT(self):self.progress()
    def do_PATCH(self):self.progress()
    def do_DELETE(self):self.progress()
    def log_message(self,fmt,*args):print("[HTTP]",fmt%args)

if __name__=="__main__":
    if os.name=='nt':
        import signal
        signal.signal(signal.SIGBREAK,signal.default_int_handler)
    for d in (ARCHIVE_DIR,STATE_DIR,CAPTURES_DIR,PROGRESS_DIR):d.mkdir(parents=True,exist_ok=True)
    import archive_db
    archive_db.initialize(STATE_DIR)
    print(f"IZZI Offline Library: http://{CLIENT_HOST}:{PORT}/")
    print(f"Listening on {HOST}:{PORT}; LAN access: http://<computer IPv4>:{PORT}/")
    try:
        RUNNING_SERVER=ThreadingHTTPServer((HOST,PORT),H)
        if os.environ.get('IZZI_START_CAPTURE')=='1' and not operations.capture_port_busy():
            try:operations.tasks.start('capture')
            except (OSError,ValueError) as error:print('[STARTUP CAPTURE]',error)
        RUNNING_SERVER.serve_forever()
    finally:
        import video_resume
        video_resume.jobs.stop()
        operations.tasks.close()
        if RUNNING_SERVER:RUNNING_SERVER.server_close()
    if RESTART_REQUESTED:sys.exit(75)
