"""Explicit lesson links and the GET dependencies loaded through the capture proxy."""
import ipaddress,re
from urllib.parse import urlsplit,urljoin
from pathlib import Path
from config import STATE_DIR
from import_har import load,save
from replay_resolver import find,usable_body
FILE=STATE_DIR/'lesson_links.json'
HOST_CACHE=None
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
    p=urlsplit(value);return p._replace(fragment='').geturl()

def register(value):
    if not valid_url(value):raise ValueError('Unsupported link URL')
    value=normalized(value);data=load(FILE,{})
    data.setdefault(value,{'resources':[value]});save(FILE,data)

def hosts():
    global HOST_CACHE
    from archive_state import load as cached_load
    data=cached_load(FILE,{})
    if HOST_CACHE and HOST_CACHE[0] is data:return HOST_CACHE[1]
    result=frozenset(urlsplit(url).hostname for entry in data.values() for url in entry.get('resources',[]) if valid_url(url))
    HOST_CACHE=(data,result)
    return result

def associate(url,referer):
    if not valid_url(url):return
    url=normalized(url);referer=normalized(referer) if referer else ''
    data=load(FILE,{});changed=False
    for root,entry in data.items():
        resources=entry.get('resources',[])
        if url==root or referer in resources or (referer and urlsplit(referer).path in ('','/') and urlsplit(referer).hostname in {urlsplit(r).hostname for r in resources}):
            if url not in resources:
                if len(resources)<2000:resources.append(url)
                else:entry['truncated']=True
                changed=True
    if changed:save(FILE,data)

def status(url,mapping,archive):
    entry=load(FILE,{}).get(normalized(url),{});resources=entry.get('resources',[url]);missing=[]
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
    if not any(url in entry.get('resources',[]) for entry in load(FILE,{}).values()):return
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
    for value in links:
        if value and not value.startswith(('#','data:','blob:')):associate(urljoin(url,value),url)
