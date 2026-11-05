"""Persistent, content-versioned coverage for the interactive flipbook pilot.

Contains resource URLs and component labels, never request headers or answers.
SQLite connections are closed per operation (including on Windows).
"""
import hashlib,json,re,sqlite3,time
from contextlib import closing
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,parse_qsl
from replay_resolver import find,usable_body,_izzi_host
from cache_bust_recovery import canonical_url
import bundled_assets,geogebra_runtime

STATES={'discovered','opened','saved','verified','failed','manual'}
COMPLETE={'saved','verified'}
MAX_ITEMS=1000
MAX_ASSETS=2000
SUPPORTED={'geogebra','objects-slider','fill-in','multiple-choice','dragndrop','tinymce','image','video','audio','framer','go-to-link','listen-and-read','youtube','slide'}


def lesson_info(value):
    if not isinstance(value,str):raise ValueError('Invalid pilot lesson')
    p=urlsplit(value)
    match=re.fullmatch(r'/DOS/(\d+)/(\d+)\.html',p.path)
    if p.scheme not in ('http','https') or p.hostname!='bg.izzi.digital' or p.username or p.password or p.port not in (None,80,443) or not match:raise ValueError('Invalid pilot lesson')
    return match[1],p.path,'https://bg.izzi.digital'+p.path


def safe_asset(value):
    if not isinstance(value,str) or len(value)>4096:return None
    try:
        p=urlsplit(value)
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.port not in (None,80,443):return None
        if p.path.startswith('/__offline_capture__/'):return None
        if any(re.search(r'(?:token|jwt|password|session|secret|authorization)',k,re.I) for k,_ in parse_qsl(p.query)):return None
        if _izzi_host(p.hostname) and p.path.startswith('/api/'):return None
        return canonical_url(urlunsplit(p._replace(fragment='')))
    except ValueError:return None


class Inventory(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.rows=[];self.is_page=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='body':self.is_page=a.get('data-page-template')=='pdf_page'
        if tag!='izzi-block':return
        identifier=a.get('block-id','');kind=a.get('block-type','unknown')
        if not identifier.isdecimal() or len(identifier)>30:raise ValueError('Invalid component ID')
        parent=self.stack[-1][0] if self.stack else ''
        panel=self.stack[0][1] if self.stack else identifier
        self.rows.append({'key':'block:'+identifier,'parent':'block:'+parent if parent else '', 'panel':panel,'kind':kind[:60],'title':kind+' #'+identifier})
        self.stack.append((identifier,panel))
        if len(self.rows)>MAX_ITEMS:raise ValueError('Too many pilot components')
    def handle_endtag(self,tag):
        if tag=='izzi-block' and self.stack:self.stack.pop()


def connection(state):
    path=Path(state)/'capture_pilot.sqlite3';path.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(path,timeout=20);con.row_factory=sqlite3.Row
    con.executescript('''
      CREATE TABLE IF NOT EXISTS pages(book TEXT,lesson TEXT,revision TEXT,state TEXT,reason TEXT,updated REAL,source TEXT,version TEXT,page_number INTEGER,book_title TEXT,viewer TEXT,page_assets TEXT,PRIMARY KEY(book,lesson));
      CREATE TABLE IF NOT EXISTS items(book TEXT,lesson TEXT,key TEXT,parent TEXT,panel TEXT,kind TEXT,title TEXT,state TEXT,reason TEXT,proof TEXT,updated REAL,PRIMARY KEY(book,lesson,key));
      CREATE INDEX IF NOT EXISTS items_book ON items(book,lesson);
    ''')
    columns={r[1] for r in con.execute('PRAGMA table_info(pages)')}
    for name in ('source','version'):
        if name not in columns:con.execute('ALTER TABLE pages ADD COLUMN '+name+" TEXT DEFAULT ''")
    if 'page_number' not in columns:con.execute('ALTER TABLE pages ADD COLUMN page_number INTEGER')
    if 'book_title' not in columns:con.execute("ALTER TABLE pages ADD COLUMN book_title TEXT DEFAULT ''")
    if 'viewer' not in columns:con.execute("ALTER TABLE pages ADD COLUMN viewer TEXT DEFAULT ''")
    if 'page_assets' not in columns:con.execute("ALTER TABLE pages ADD COLUMN page_assets TEXT DEFAULT '[]'")
    return con


def youtube_file(url,archive):
    from youtube_download import video_id
    identifier=video_id(url)
    if not identifier:return None
    for ext in ('.mp4','.webm'):
        file=Path(archive)/'youtube'/(identifier+ext)
        if not file.is_file() or file.stat().st_size<=16:continue
        with file.open('rb') as stream:header=stream.read(16)
        if (ext=='.mp4' and b'ftyp' in header) or (ext=='.webm' and header.startswith(b'\x1aE\xdf\xa3')):return file
    return None


def assets_available(assets,mapping,archive):
    import external_links
    from youtube_download import video_id
    from resource_policy import optional_reason
    for value in assets:
        url=safe_asset(value)
        if not url:return False
        if optional_reason(url):continue
        if video_id(url):
            if not youtube_file(url,archive):return False
            continue
        p=urlsplit(url);ext=Path(p.path).suffix.lower()
        if not find(mapping,p.hostname,p.path,p.query,lambda row:usable_body(row,archive,ext)) and not bundled_assets.asset(p.hostname,p.path) and not geogebra_runtime.asset(p.hostname,p.path):return False
        # A linked application's HTML alone is not sufficient after resources are removed.
        if url in external_links.state()['data'] and not external_links.status(url,mapping,archive)['available']:return False
    return True


def assets_fingerprint(assets,mapping,archive):
    from resource_policy import optional_reason
    entries=[]
    for url in sorted(assets):
        if optional_reason(url):continue
        youtube=youtube_file(url,archive)
        if youtube:
            info=youtube.stat();entries.append((url,str(youtube),info.st_size,info.st_mtime_ns,info.st_ctime_ns));continue
        p=urlsplit(url)
        row=find(mapping,p.hostname,p.path,p.query,lambda r:usable_body(r,archive,Path(p.path).suffix.lower()))
        if row:entries.append((url,row['key']))
        else:
            file=bundled_assets.asset(p.hostname,p.path) or geogebra_runtime.asset(p.hostname,p.path)
            if not file:return ''
            info=file.stat();entries.append((url,str(file),info.st_size,info.st_mtime_ns,info.st_ctime_ns))
    return hashlib.sha256(json.dumps(entries).encode()).hexdigest()


def check_page_source(page,mapping,archive):
    row=find(mapping,'bg.izzi.digital',page['lesson'],'',lambda r:usable_body(r,archive,'.html'))
    if not row or row['key']!=page['source']:raise ValueError('HTML на страницата е променен. Повтори проверката от началото.')


def begin(state,lesson,version,mapping,archive,page_number=None,viewer=None,page_assets=None):
    book,path,url=lesson_info(lesson)
    viewer_path=''
    if viewer is not None:
        viewer_book,viewer_path,_=lesson_info(viewer)
        if viewer_book!=book:raise ValueError('Viewer belongs to another book')
    page_assets=page_assets or []
    if not isinstance(page_assets,list) or len(page_assets)>2 or any(not safe_asset(a) for a in page_assets):raise ValueError('Invalid page images')
    if page_number is not None and (type(page_number) is not int or not 0<=page_number<=10000):raise ValueError('Invalid page number')
    if not re.fullmatch(r'[a-f0-9]{12}',version or ''):raise ValueError('Invalid capture version')
    row=find(mapping,'bg.izzi.digital',path,'',lambda r:usable_body(r,archive,'.html'))
    if not row:raise ValueError('HTML на страницата още не е записан в архива. Повтори проверката.')
    revision=hashlib.sha256((row['key']+'\n'+version).encode()).hexdigest()
    parser=Inventory()
    with (Path(archive)/row['key']).open('rb') as stream:body=stream.read(32*1024*1024+1)
    if len(body)>32*1024*1024:raise ValueError('Pilot page exceeds 32 MiB')
    text=body.decode('utf-8');parser.feed(text)
    book_title=''
    marker=re.search(r'\bvar\s+dosData\s*=\s*',text)
    if marker:
        try:book_title=str(json.JSONDecoder().raw_decode(text[marker.end():])[0].get('publicationName',''))[:200]
        except (ValueError,AttributeError):pass
    if not parser.is_page:raise ValueError('Pilot requires a flipbook page')
    with closing(connection(state)) as con,con:
        old=con.execute('SELECT * FROM pages WHERE book=? AND lesson=?',(book,path)).fetchone()
        if not old or old['revision']!=revision:con.execute('DELETE FROM items WHERE book=? AND lesson=?',(book,path))
        con.execute('INSERT OR REPLACE INTO pages(book,lesson,revision,state,reason,updated,source,version,page_number,book_title,viewer,page_assets) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(book,path,revision,'running','',time.time(),row['key'],version,page_number,book_title,viewer_path,json.dumps(page_assets)))
        for item in parser.rows:
            con.execute('INSERT OR IGNORE INTO items VALUES(?,?,?,?,?,?,?,?,?,?,?)',(book,path,item['key'],item['parent'],item['panel'],item['kind'],item['title'],'discovered','', '{}',time.time()))
        rows=con.execute('SELECT * FROM items WHERE book=? AND lesson=?',(book,path)).fetchall()
        verified=[]
        for item in rows:
            if item['state'] in COMPLETE:
                proof=json.loads(item['proof'])
                if proof.get('assets') and assets_available(proof['assets'],mapping,archive) and proof.get('fingerprint')==assets_fingerprint(proof['assets'],mapping,archive):verified.append(item['key'])
                else:con.execute("UPDATE items SET state='discovered',reason='Ресурсите трябва да се проверят отново' WHERE book=? AND lesson=? AND key=?",(book,path,item['key']))
        inventory=[dict(r) for r in con.execute('SELECT key,parent,panel,kind,title,state FROM items WHERE book=? AND lesson=?',(book,path))]
        return {'capture':True,'revision':revision,'inventory':inventory,'verified':verified}


def record(state,data,mapping,archive):
    book,path,url=lesson_info(data.get('lesson'));key=data.get('key','');status=data.get('state','')
    if not isinstance(key,str) or not re.fullmatch(r'(?:block:\d+|slide:\d+:\d+)',key) or status not in STATES:raise ValueError('Invalid pilot item')
    proof=data.get('proof',{})
    if not isinstance(proof,dict) or set(proof)-{'assets','ready','embedded'}:raise ValueError('Invalid pilot proof')
    assets=proof.get('assets',[])
    if not isinstance(assets,list) or len(assets)>MAX_ASSETS or any(safe_asset(a) is None for a in assets):raise ValueError('Invalid pilot resources')
    proof={'assets':sorted(set(safe_asset(a) for a in assets)),'ready':proof.get('ready') is True,'embedded':proof.get('embedded') is True}
    with closing(connection(state)) as con,con:
        page=con.execute('SELECT * FROM pages WHERE book=? AND lesson=?',(book,path)).fetchone()
        if not page or page['revision']!=data.get('revision'):raise ValueError('Страницата е променена. Започни проверката отново.')
        check_page_source(page,mapping,archive)
        item=con.execute('SELECT * FROM items WHERE book=? AND lesson=? AND key=?',(book,path,key)).fetchone()
        if not item:
            match=re.fullmatch(r'slide:(\d+):(\d+)',key)
            if not match or not 1<=int(match[2])<=200:raise ValueError('Unknown pilot component')
            parent=con.execute('SELECT * FROM items WHERE book=? AND lesson=? AND key=?',(book,path,'block:'+match[1])).fetchone()
            if not parent or parent['kind']!='objects-slider':raise ValueError('Unknown slider')
            if con.execute('SELECT COUNT(*) FROM items WHERE book=? AND lesson=?',(book,path)).fetchone()[0]>=MAX_ITEMS:raise ValueError('Too many pilot items')
            con.execute('INSERT INTO items VALUES(?,?,?,?,?,?,?,?,?,?,?)',(book,path,key,parent['key'],parent['panel'],'slide', 'Слайд '+match[2],'discovered','','{}',time.time()))
            item=con.execute('SELECT * FROM items WHERE book=? AND lesson=? AND key=?',(book,path,key)).fetchone()
        if status in COMPLETE:
            if item['kind'] not in SUPPORTED:raise ValueError('Непознат компонент изисква ръчна проверка.')
            for required in [url]+(['https://bg.izzi.digital'+page['viewer']] if page['viewer'] else []):
                if required not in proof['assets']:proof['assets'].append(required)
            if not assets_available(proof['assets'],mapping,archive):raise ValueError('Ресурсите на задачата не са потвърдени в архива.')
            if item['kind']=='geogebra':
                if not proof['ready'] or (not proof['embedded'] and not any(urlsplit(a).path.lower().endswith('.ggb') for a in proof['assets'])):raise ValueError('GeoGebra аплетът не е потвърдил готовност.')
        if status in COMPLETE:proof['fingerprint']=assets_fingerprint(proof['assets'],mapping,archive)
        parent=data.get('parent',item['parent'])
        if parent!=item['parent']:
            target=con.execute('SELECT panel FROM items WHERE book=? AND lesson=? AND key=?',(book,path,parent)).fetchone()
            if not re.fullmatch(r'slide:\d+:\d+',parent) or not target or target['panel']!=item['panel'] or key=='block:'+item['panel']:raise ValueError('Invalid pilot parent')
        title=data.get('title',item['title']);reason=data.get('reason','')
        if not isinstance(title,str) or not isinstance(reason,str):raise ValueError('Invalid pilot text')
        con.execute('UPDATE items SET title=?,state=?,reason=?,proof=?,updated=?,parent=? WHERE book=? AND lesson=? AND key=?',(re.sub('<[^>]*>',' ',title)[:300],status,reason[:1000],json.dumps(proof),time.time(),parent,book,path,key))
        return {'capture':True,'saved':True}


def finish(state,data,mapping,archive):
    book,path,url=lesson_info(data.get('lesson'))
    with closing(connection(state)) as con,con:
        page=con.execute('SELECT * FROM pages WHERE book=? AND lesson=?',(book,path)).fetchone()
        if not page or page['revision']!=data.get('revision'):raise ValueError('Invalid pilot revision')
        check_page_source(page,mapping,archive)
        rows=con.execute('SELECT key,state,proof FROM items WHERE book=? AND lesson=?',(book,path)).fetchall()
        missing=[]
        for r in rows:
            proof=json.loads(r['proof']);assets=proof.get('assets',[])
            if r['state'] not in COMPLETE or not assets or not assets_available(assets,mapping,archive) or proof.get('fingerprint')!=assets_fingerprint(assets,mapping,archive):missing.append(r['key'])
        page_assets=[url]+json.loads(page['page_assets'] or '[]')+(['https://bg.izzi.digital'+page['viewer']] if page['viewer'] else [])
        if not assets_available(page_assets,mapping,archive):missing.append('page')
        con.execute('UPDATE pages SET state=?,reason=?,updated=? WHERE book=? AND lesson=?',('complete' if not missing else 'incomplete',', '.join(missing)[:1000],time.time(),book,path))
        return {'capture':True,'available':not missing,'missing':missing}


def report(state,book=None):
    if book is not None and not re.fullmatch(r'\d+',str(book)):raise ValueError('Invalid book')
    if not (Path(state)/'capture_pilot.sqlite3').is_file():return {'pages':[],'offline_tested':False}
    with closing(connection(state)) as con:
        rows=con.execute('SELECT * FROM pages'+(' WHERE book=?' if book is not None else '')+' ORDER BY updated DESC LIMIT 2000',(str(book),) if book is not None else ()).fetchall()
        pages=[];count=0;truncated=False
        for row in rows:
            if count>=20000:truncated=True;break
            page=dict(row)
            page['items']=[{k:r[k] for k in ('key','parent','panel','kind','title','state','reason','updated')} for r in con.execute('SELECT * FROM items WHERE book=? AND lesson=? ORDER BY rowid LIMIT ?',(row['book'],row['lesson'],20000-count))]
            count+=len(page['items'])
            pages.append(page)
        return {'pages':pages,'truncated':truncated,'offline_tested':False,'note':'Отчет от capture; не доказва оценяване или работа на външни сървъри без интернет.'}


def display_links(state,book):
    """Keep stored lesson identity, but open a captured flipbook at its page."""
    if not (Path(state)/'capture_pilot.sqlite3').is_file():return {}
    with closing(connection(state)) as con:
        links={}
        for row in con.execute('SELECT lesson,viewer,page_number FROM pages WHERE book=?',(str(book),)):
            number=row['page_number'];viewer=row['viewer']
            if type(number) is int and 0<=number<=10000 and re.fullmatch(r'/DOS/'+re.escape(str(book))+r'/\d+\.html',viewer or ''):
                links[row['lesson']]=viewer+'?page='+str(number)+'&centrespread=0'
        return links
