"""Current-lesson GET requests and archive confirmation for strict browser capture."""
import threading,time
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
from replay_resolver import find,pick,usable_body,_izzi_host
from cache_bust_recovery import canonical_url
import geogebra_runtime
import bundled_assets
import geogebra_capture
from resource_policy import optional_reason
LOCK=threading.RLock()
CURRENT=None
LIMIT=2000

def valid(value):
    try:
        p=urlsplit(value)
        return p.scheme in ('http','https') and _izzi_host(p.hostname) and not p.username and not p.password and p.port in (None,80,443) and not p.path.startswith('/__offline_capture__/')
    except (ValueError,TypeError):return False

def start(lesson):
    global CURRENT
    if not valid(lesson):return
    with LOCK:CURRENT={'lesson':canonical_url(lesson),'urls':set(),'pending':{},'activity':time.monotonic(),'truncated':False}

def expect(url,lesson):
    """A declared linked app may send only an origin Referer across hosts."""
    if not valid(url) or not valid(lesson):return False
    url=canonical_url(url)
    with LOCK:
        if not CURRENT or CURRENT['lesson']!=canonical_url(lesson):return False
        if len(CURRENT['urls'])>=LIMIT and url not in CURRENT['urls']:CURRENT['truncated']=True;return False
        CURRENT['urls'].add(url)
        if not optional_reason(url):CURRENT['activity']=time.monotonic()
        return True

def follow_redirect(source,target):
    """Carry current-lesson ownership across an origin-only redirect Referer."""
    if not valid(target):return False
    with LOCK:
        if not CURRENT or canonical_url(source) not in CURRENT['urls']:return False
        return expect(target,CURRENT['lesson'])

def watch(url,method,referer,identifier):
    if method!='GET' or not valid(url):return False
    url=canonical_url(url);referer=canonical_url(referer) if referer else ''
    with LOCK:
        if not CURRENT or (url!=CURRENT['lesson'] and url not in CURRENT['urls'] and referer!=CURRENT['lesson'] and referer not in CURRENT['urls']):return False
        if len(CURRENT['urls'])>=LIMIT and url not in CURRENT['urls']:CURRENT['truncated']=True;return False
        CURRENT['urls'].add(url);CURRENT['pending'][identifier]=url
        if not optional_reason(url):CURRENT['activity']=time.monotonic()
        return True

def finish(identifier):
    with LOCK:
        if CURRENT and identifier in CURRENT['pending']:
            url=CURRENT['pending'].pop(identifier)
            if not optional_reason(url):CURRENT['activity']=time.monotonic()

def status(lesson,assets,mapping,archive,geogebra_blocks=()):
    if not valid(lesson) or not isinstance(assets,list) or len(assets)>LIMIT:raise ValueError('Invalid lesson resource list')
    with LOCK:
        current=CURRENT if CURRENT and CURRENT['lesson']==canonical_url(lesson) else None
        urls=set(current['urls']) if current else set();pending=list(current['pending'].values()) if current else []
        quiet=time.monotonic()-current['activity'] if current else 0
        truncated=bool(current and current['truncated'])
    urls.add(canonical_url(lesson))
    urls.update(canonical_url(value) for value in assets if isinstance(value,str) and valid(value))
    urls={geogebra_capture.replacement(url,lesson,geogebra_blocks) or url for url in urls}
    urls={urlunsplit(urlsplit(url)._replace(path=geogebra_capture.normalize_path(urlsplit(url).path))) for url in urls}
    import external_links
    urls-=external_links.false_css_dependencies(urls,mapping,archive)
    missing=[];warnings=[]
    pending=[url for url in pending if not optional_reason(url)]
    for url in sorted(urls):
        p=urlsplit(url);ext=Path(p.path).suffix.lower()
        records=mapping.get(url,[])
        row=pick(records,lambda r:usable_body(r,archive,ext)) if p.path.startswith('/api/') else find(mapping,p.hostname,p.path,p.query,lambda r:usable_body(r,archive,ext))
        if row or bundled_assets.asset(p.hostname,p.path) or geogebra_runtime.asset(p.hostname,p.path) or any(r.get('method','GET')=='GET' and r.get('status')==204 for r in records):continue
        statuses=[r.get('status') for r in records if r.get('method','GET')=='GET']
        code=statuses[-1] if statuses else None
        reason=('HTTP '+str(code)+' от оригиналния сайт') if isinstance(code,int) and code>=400 else 'Няма потвърден годен файл в архива'
        optional=optional_reason(url)
        (warnings if optional else missing).append({'kind':'asset','url':url,'reason':reason,'severity':'warning' if optional else 'required','policy_reason':optional})
    return {'capture':True,'available':bool(current) and not pending and quiet>=1 and not missing and not truncated,'tracked':bool(current),'quiet_ms':int(quiet*1000),'pending':pending,'missing':missing,'warnings':warnings,'limit_reached':truncated}
