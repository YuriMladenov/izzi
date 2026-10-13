"""Inspect incomplete MP4 coverage and resume missing bytes through capture proxy."""
import hashlib,json,ssl,threading,urllib.request,urllib.error
from pathlib import Path
from urllib.parse import urlsplit
from collections import deque
from config import ARCHIVE_DIR,STATE_DIR,URL_MAP_FILE,CAPTURE_PROXY_PORT
from import_har import load
from replay_resolver import find,usable_body
from range_assembler import RX,merged,uid,valid_part
CHUNK=4*1024*1024
MAX_VIDEO=250*1024*1024

def safe_url(url):
    try:
        p=urlsplit(url)
        return p.scheme=='https' and not p.username and not p.password and p.port in (None,443) and bool(p.hostname) and (p.hostname=='izzi.digital' or p.hostname.endswith('.izzi.digital')) and p.path.lower().endswith('.mp4')
    except ValueError:return False

def local_part(path,identity,start,end):
    # Manifests moved from another Windows computer can contain old absolute paths.
    expected=STATE_DIR/'range_assembly'/identity/f'{start}-{end}.part'
    candidate=Path(path)
    return candidate if candidate.resolve()==expected.resolve() else expected

def gaps(ranges,total):
    out=[];pos=0
    for start,end in merged(ranges):
        if start>pos:out.append([pos,start-1])
        pos=max(pos,end+1)
    if pos<total:out.append([pos,total-1])
    return out

def inspect():
    mapping=load(URL_MAP_FILE,{})
    urls={url for url in mapping if safe_url(url)}
    manifests={};errors=[]
    for path in sorted((STATE_DIR/'range_assembly').glob('*.json')):
        try:
            data=json.loads(path.read_text(encoding='utf8'));url=data.get('url','')
            if not safe_url(url):continue
            if path.stem!=uid(url) or not isinstance(data.get('total'),int) or data['total']<=0 or not isinstance(data.get('ranges'),list):raise ValueError('Невалиден manifest')
            manifests[url]=data;urls.add(url)
        except (OSError,ValueError,AttributeError) as error:errors.append(path.name+': '+str(error))
    rows=[]
    for url in sorted(urls):
        p=urlsplit(url)
        full=find(mapping,p.hostname,p.path,p.query,lambda row:usable_body(row,ARCHIVE_DIR,'.mp4'))
        if full:continue
        identity=uid(url);data=manifests.get(url,{});total=data.get('total');ranges=[]
        for record in mapping.get(url,[]):
            match=RX.fullmatch(str(record.get('content_range','')))
            if match and match[3]!='*' and not total:total=int(match[3])
        for part in data.get('ranges',[]):
            try:
                start,end,name=part
                if not isinstance(start,int) or not isinstance(end,int) or not 0<=start<=end<total:continue
                path=local_part(name,identity,start,end)
                if valid_part(path,start,end):ranges.append([start,end])
            except (ValueError,TypeError,OSError):continue
        # Archived 206 bodies also count; the proxy can import them into range assembly.
        for record in mapping.get(url,[]):
            match=RX.fullmatch(str(record.get('content_range','')))
            if not match or match[3]=='*' or int(match[3])!=total or (data.get('validator') and record.get('validator')!=data['validator']) or record.get('status')!=206 or not record.get('body_available'):continue
            start,end=int(match[1]),int(match[2]);path=ARCHIVE_DIR/str(record.get('key',''))
            if 0<=start<=end<total and path.resolve().is_relative_to(ARCHIVE_DIR.resolve()) and valid_part(path,start,end):ranges.append([start,end])
        ranges=merged(ranges);covered=sum(end-start+1 for start,end in ranges)
        rows.append({'id':identity,'url':url,'label':p.hostname+p.path,'total':total,'covered':covered,'missing':gaps(ranges,total) if total else [],'percent':round(100*covered/total,1) if total else 0})
    return {'videos':rows,'errors':errors}

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not safe_url(newurl):raise ValueError('Пренасочването е извън поддържаните IZZI MP4 адреси.')
        # The proxy keeps credentials scoped to the exact original URL.
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def opener():
    cert=Path.home()/'.mitmproxy'/'mitmproxy-ca-cert.pem'
    if not cert.is_file():raise ValueError('Липсва сертификатът на capture proxy в .mitmproxy. Стартирай capture_mode.bat.')
    context=ssl.create_default_context();context.load_verify_locations(cafile=str(cert))
    proxy=f'http://127.0.0.1:{CAPTURE_PROXY_PORT}'
    return urllib.request.build_opener(urllib.request.ProxyHandler({'http':proxy,'https':proxy}),urllib.request.HTTPSHandler(context=context),SafeRedirect())

def fetch(client,url,start,end):
    request=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}','X-IZZI-Resume':'1','Accept-Encoding':'identity','Cache-Control':'no-cache'})
    with client.open(request,timeout=45) as response:
        if response.status not in (200,206):raise ValueError('Неподдържан отговор от сайта')
        size=int(response.headers.get('Content-Length') or '0')
        if size>MAX_VIDEO:raise ValueError('Видеото надвишава лимита от 250 MiB.')
        transferred=0
        for block in iter(lambda:response.read(1024*1024),b''):
            transferred+=len(block)
            if transferred>MAX_VIDEO:raise ValueError('Видеото надвишава лимита от 250 MiB.')
        if response.status==206:
            match=RX.fullmatch(response.headers.get('Content-Range',''))
            if not match or match[3]=='*' or int(match[1])!=start:raise ValueError('Сайтът върна различен byte range.')
        return transferred

class Jobs:
    def __init__(self):self.lock=threading.RLock();self.cancel=threading.Event();self.state='idle';self.lines=deque(maxlen=200);self.results=[];self.current=None
    def snapshot(self):
        with self.lock:return {'state':self.state,'log':'\n'.join(self.lines),'results':list(self.results),'current':self.current}
    def note(self,text):
        with self.lock:self.lines.append(text)
    def start(self,identifier='all'):
        import operations
        if not operations.capture_port_busy():raise ValueError('Първо стартирай capture_mode.bat или Capture от WebUI.')
        report=inspect()
        if report['errors']:raise ValueError('Има нечетими range manifests. Първо провери архива.')
        videos=[row for row in report['videos'] if identifier=='all' or row['id']==identifier]
        if not videos:raise ValueError('Няма недовършени видеа в този избор.')
        with self.lock:
            if self.state=='running':raise ValueError('Вече се изтеглят видеа.')
            self.cancel.clear();self.results=[];self.lines.clear();self.state='running'
        threading.Thread(target=self.run,args=(videos,),daemon=True).start()
    def stop(self):self.cancel.set()
    def run(self,videos):
        failed=False
        try:
            client=opener()
            for selected in videos:
                if self.cancel.is_set():break
                with self.lock:self.current=selected['id']
                self.note('Изтегляне: '+selected['label'])
                try:
                    # Fresh inspection after every range catches completed files and changed totals.
                    for _ in range(MAX_VIDEO//CHUNK+2):
                        if self.cancel.is_set():break
                        row=next((r for r in inspect()['videos'] if r['id']==selected['id']),None)
                        if row is None:
                            with self.lock:self.results.append({'id':selected['id'],'state':'complete'})
                            self.note('Готово: '+selected['label']);break
                        if row['total'] and row['total']>MAX_VIDEO:raise ValueError('Видеото надвишава лимита от 250 MiB.')
                        if row['total'] and not row['missing']:
                            # The proxy assembles already archived 206 parts when receiving this header.
                            start,end=0,min(CHUNK-1,row['total']-1)
                        elif row['missing']:start,end=row['missing'][0];end=min(end,start+CHUNK-1)
                        else:start,end=0,CHUNK-1
                        before=(row['covered'],row['total'])
                        fetch(client,row['url'],start,end)
                        after=next((r for r in inspect()['videos'] if r['id']==selected['id']),None)
                        if after is None:
                            with self.lock:self.results.append({'id':selected['id'],'state':'complete'})
                            self.note('Готово: '+selected['label']);break
                        if before==(after['covered'],after['total']):raise ValueError('Няма напредък. Провери capture proxy и достъпа до оригиналния урок.')
                        if after:self.note('Получени %.1f%% · %s'%(after['percent'],selected['label']))
                    else:raise ValueError('Лимитът за заявки е достигнат; повтори проверката.')
                except urllib.error.HTTPError as error:
                    failed=True;message='HTTP '+str(error.code)
                    if error.code in (401,403):message+=': отвори видеото в оригиналния урок с правилния профил и активен capture, после опитай отново.'
                    self.note(message+' · '+selected['label'])
                    with self.lock:self.results.append({'id':selected['id'],'state':'failed','error':message})
                except (OSError,ValueError,urllib.error.URLError) as error:
                    failed=True;message=str(error)
                    self.note(message+' · '+selected['label'])
                    with self.lock:self.results.append({'id':selected['id'],'state':'failed','error':message})
        except (OSError,ValueError) as error:failed=True;self.note(str(error))
        finally:
            with self.lock:self.current=None;self.state='stopped' if self.cancel.is_set() else 'failed' if failed else 'success'
jobs=Jobs()
