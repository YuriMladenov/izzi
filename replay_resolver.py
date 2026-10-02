"""Shared URL-map resolution for HTTP replay and archive diagnostics."""
import re
from pathlib import Path
from urllib.parse import urlparse,unquote

def score(r):
    if not isinstance(r,dict) or not r.get("body_available") or not r.get("key"): return -10000
    s=0
    if r.get("method","GET")=="GET": s+=100
    if r.get("complete"): s+=1000
    if r.get("status")==200: s+=300
    elif r.get("status")==206: s-=300
    if r.get("decoded"): s+=200
    if r.get("source")=="capture_proxy_v3.2": s+=100
    return s

def complete_range(r,size=None):
    """A single 206 body is complete only when it proves exact full coverage."""
    cr=re.fullmatch(r'bytes\s+(\d+)-(\d+)/(\d+)',str(r.get('content_range','')).strip(),re.I)
    if not cr:return False
    start,end,total=map(int,cr.groups())
    if size is None:size=r.get('size')
    return total>0 and start==0 and end==total-1 and size==total

def complete_body(r,size=None):
    return bool(r.get('complete') or r.get('source')=='assembled_ranges' or complete_range(r,size))

def usable_body(r,archive,ext=''):
    if not isinstance(r,dict) or not r.get('body_available') or not isinstance(r.get('key'),str) or not r['key']:return False
    blob=Path(archive)/r['key']
    if not blob.is_file():return False
    if r.get('status',200) not in (200,206):return False
    if r.get('size') is not None and blob.stat().st_size!=r['size']:return False
    if r.get('status')==206 and not complete_body(r,blob.stat().st_size):return False
    if ext in {'.woff','.woff2','.ttf','.otf'}:
        with blob.open('rb') as stream:magic=stream.read(4)
        if magic not in (b'wOF2',b'wOFF',b'OTTO',b'\x00\x01\x00\x00',b'ttcf',b'true'):return False
    if ext in {'.svg','.png','.jpg','.jpeg','.webp','.gif'}:
        with blob.open('rb') as stream:header=stream.read(1024)
        if not header or re.search(br'<(?:!doctype\s+html|html)\b',header,re.I):return False
    return True

def pick(rs,usable=None):
    good=[r for r in (rs or []) if score(r)>-10000 and (usable is None or usable(r))]
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

def book_ids(path):
    return set(re.findall(r'(?:^/DOS/|/publication/)(\d+)(?:/|$)',unquote(path)))

def compatible_books(requested,candidate,book=None):
    wanted=book_ids(requested)
    if book:wanted.add(str(book))
    found=book_ids(candidate)
    return len(wanted)<=1 and len(found)<=1 and (not wanted or not found or wanted==found)

def find(m,host,path,q,usable=None,book=None):
    """Resolve from the URL map itself.

    Exact URL is preferred. For IZZI resources we then compare canonical paths
    using parsed hostname (not netloc), so :443 / captured-host variations do
    not make an otherwise valid archived body unreachable.
    """
    requested_path=unquote(path)
    if not compatible_books(requested_path,requested_path,book):return None
    exact=[]
    for scheme in ("https","http"):
        for h in (host, host.split(":",1)[0]):
            u=f"{scheme}://{h}{requested_path}"+(("?"+q) if q else "")
            r=pick(m.get(u),usable)
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
        if not compatible_books(requested_path,pp.path,book):continue
        r=pick(rs,usable)
        if not r: continue
        # Query is a preference, not a requirement. Cache-bust recovery stored
        # the body under the original canonical URL.
        qbonus=3 if pp.query==q else (2 if not q else 1)
        # Prefer the original bg host if several IZZI hosts share a path.
        hbonus=1 if (pp.hostname or "").lower()=="bg.izzi.digital" else 0
        hits.append((qbonus,hbonus,score(r),r,u))
    if hits:
        # Unscoped shared routes must not choose one book's private resource
        # by record order when different books have different archived bodies.
        if not book and not book_ids(requested_path):
            scopes=set().union(*(book_ids(urlparse(x[4]).path) for x in hits))
            if len(scopes)>1 and len({x[3].get("key") for x in hits})>1:return None
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
                r=pick(rs,usable)
                if r: lessons.append((score(r),r,u))
        if lessons:
            lessons.sort(key=lambda x:x[0],reverse=True)
            print("[LESSON FALLBACK]",requested_path,"=>",lessons[0][2])
            return lessons[0][1]
    return None
