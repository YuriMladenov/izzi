"""Explicit lesson links and the GET dependencies loaded through the capture proxy."""
import ipaddress,re,threading
from urllib.parse import urlsplit,urljoin
from pathlib import Path
from config import STATE_DIR
from import_har import load,save
from replay_resolver import find,usable_body
from cache_bust_recovery import canonical_url
FILE=STATE_DIR/'lesson_links.json'
LOCK=threading.RLock()
INDEX=None
BLOCKED=('google-analytics.com','googletagmanager.com','youtube.com','youtube-nocookie.com','doubleclick.net')

def valid_url(value):
    try:
        p=urlsplit(value)
        if p.scheme not in ('http','https') or p.username or p.password or p.port not in (None,80,443):return False
        host=p.hostname or ''
        if not re.fullmatch(r'[a-zA-Z0-9.-]+',host) or '.' not in host or host.endswith(('.local','.localhost')):return False
        if any(host==h or host.endswith('.'+h) for h in BLOCKED):return False
        try:ipaddress.ip_address(host);return False
        except ValueError:pass
        return True
    except ValueError:return False

def normalized(value):
    return canonical_url(value)

def stamp():
    try:
        info=FILE.stat();return str(FILE.resolve()),info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns
    except FileNotFoundError:return str(FILE.resolve()),None

def state():
    """Indexes avoid rereading/scanning a large dependency JSON per request."""
    global INDEX
    signature=stamp()
    if INDEX is not None and INDEX['stamp']==signature:return INDEX
    data=load(FILE,{})
    owners={};by_host={}
    for root,entry in data.items():
        for value in [root,*entry.get('resources',[])]:
            if not valid_url(value):continue
            value=normalized(value);owners.setdefault(value,set()).add(root)
            by_host.setdefault(urlsplit(value).hostname,set()).add(root)
    INDEX={'stamp':signature,'data':data,'owners':owners,'by_host':by_host,'hosts':frozenset(by_host)}
    return INDEX

def commit(data):
    current=state();save(FILE,data)
    current['data']=data;current['stamp']=stamp();current['hosts']=frozenset(current['by_host'])

def register(value):
    if not valid_url(value):raise ValueError('Unsupported link URL')
    global INDEX
    value=normalized(value)
    with LOCK:
        current=state()
        if value in current['data']:return
        data=dict(current['data']);data[value]={'resources':[value]}
        current['owners'].setdefault(value,set()).add(value)
        current['by_host'].setdefault(urlsplit(value).hostname,set()).add(value)
        try:commit(data)
        except Exception:
            INDEX=None;raise

def hosts():
    current=INDEX
    if current is not None and current['stamp']==stamp():return current['hosts']
    with LOCK:return state()['hosts']

def associate(url,referer):
    associate_many([(url,referer)])

def associate_many(pairs):
    global INDEX
    with LOCK:
        current=state();data=dict(current['data']);changed=set()
        try:
            for url,referer in pairs:
                if not valid_url(url):continue
                url=normalized(url);referer=normalized(referer) if referer else ''
                roots=set(current['owners'].get(url,()))|set(current['owners'].get(referer,()))
                ref=urlsplit(referer)
                # Platform home/API traffic cannot identify one linked app.
                # Never attach the whole bookshelf to every IZZI link.
                if ref.path in ('','/') and ref.hostname and not (ref.hostname=='izzi.digital' or ref.hostname.endswith('.izzi.digital')):
                    roots.update(current['by_host'].get(ref.hostname,()))
                for root in roots:
                    if root in current['owners'].get(url,()):continue
                    if root not in changed:
                        data[root]={**data[root],'resources':list(data[root].get('resources',[]))};changed.add(root)
                    entry=data[root];resources=entry['resources']
                    if len(resources)>=2000:entry['truncated']=True;continue
                    resources.append(url)
                    current['owners'].setdefault(url,set()).add(root)
                    current['by_host'].setdefault(urlsplit(url).hostname,set()).add(root)
            if changed:commit(data)
        except Exception:
            INDEX=None;raise

def status(url,mapping,archive):
    with LOCK:entry=state()['data'].get(normalized(url),{})
    resources=entry.get('resources',[url]);missing=[]
    for value in resources:
        p=urlsplit(value)
        row=None;target=value
        for _ in range(10):
            p=urlsplit(target)
            row=find(mapping,p.hostname or '',p.path,p.query,lambda row:usable_body(row,archive,Path(p.path).suffix.lower()))
            if row:break
            redirect=find(mapping,p.hostname or '',p.path,p.query)
            if not redirect or not 300<=redirect.get('status',0)<400 or not redirect.get('location'):break
            target=urljoin(target,redirect['location'])
            if not valid_url(target):break
        if not row:missing.append(value)
    return {'capture':True,'available':not missing and not entry.get('truncated',False),'limit_reached':entry.get('truncated',False),'total':len(resources),'missing':missing[:30]}

def discover(url,data,content_type):
    """Track declared page/style dependencies even when iframe embedding is refused."""
    if 'text/html' not in content_type and 'text/css' not in content_type:return
    with LOCK:
        if normalized(url) not in state()['owners']:return
    text=data.decode('utf-8',errors='replace');links=[]
    if 'text/html' in content_type:
        from html.parser import HTMLParser
        class Dependencies(HTMLParser):
            def handle_starttag(self,tag,attrs):
                values=dict(attrs)
                if tag in ('script','img','iframe','source','video','audio','embed') and values.get('src'):links.append(values['src'])
                if tag=='link' and values.get('rel','').lower() in ('stylesheet','preload','modulepreload') and values.get('href'):links.append(values['href'])
        Dependencies().feed(text)
    if 'text/css' in content_type:
        links.extend(m[1].strip('"\' ') for m in re.finditer(r'url\(\s*([^)]*)\)',text))
        links.extend(re.findall(r'@import\s+["\']([^"\']+)',text))
    associate_many((urljoin(url,value),url) for value in links if value and not value.startswith(('#','data:','blob:')))
