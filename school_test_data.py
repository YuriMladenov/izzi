"""Read-only archived questions for the legacy tests.school.bg JSONP client."""
import json,re
from pathlib import Path
from urllib.parse import urlsplit
from replay_resolver import find,usable_body
HOSTS={'tests.school.bg','klett.bg'}

def test_number(url):
    p=urlsplit(url)
    match=re.fullmatch(r'/api/tests/get/(\d+)/?',p.path)
    return int(match[1]) if p.hostname in HOSTS and match else None

def endpoint(text):
    if 'https://tests.school.bg/api/tests/get/' not in text:return None
    match=re.search(r'\btestid\s*=\s*(\d+)\s*;',text)
    return 'https://tests.school.bg/api/tests/get/'+match[1]+'/' if match else None

def required(root,mapping,archive):
    p=urlsplit(root)
    if not p.path.endswith(('.html','.htm')):return None
    row=find(mapping,p.hostname or '',p.path,p.query,lambda r:usable_body(r,archive,'.html'))
    if not row:return None
    path=Path(archive)/row['key']
    if path.stat().st_size>1024*1024:return None
    text=path.read_text(encoding='utf8',errors='replace')
    target=endpoint(text)
    return target+'?testrequest=izziOfflineCapture' if target else None

def decode(data,number):
    text=data.decode('utf-8-sig').strip()
    if text.startswith('/**/'):text=text[4:].lstrip()
    match=re.fullmatch(r'[A-Za-z_$][\w$]*\s*\((.*)\)\s*;?',text,re.S)
    if match:text=match[1]
    payload=json.loads(text)
    if not isinstance(payload,dict) or not isinstance(payload.get('testinfo'),dict) or str(payload['testinfo'].get('id'))!=str(number):return None
    rows=payload.get('testdata')
    if not isinstance(rows,list) or not rows or not all(isinstance(row,dict) and isinstance(row.get('question'),dict) for row in rows):return None
    return payload

def archived(url,mapping,archive):
    number=test_number(url)
    if number is None:return None
    path=urlsplit(url).path.rstrip('/')
    candidates=mapping.replay_candidates(path+'/') if hasattr(mapping,'replay_candidates') else ((u,None,rows) for u,rows in mapping.items())
    # Legacy endpoints normally use the trailing slash; match both forms in SQLite.
    if hasattr(mapping,'replay_candidates'):
        import itertools
        candidates=itertools.chain(candidates,mapping.replay_candidates(path))
    for value,parsed,rows in candidates:
        p=parsed or urlsplit(value)
        if p.hostname not in HOSTS or p.path.rstrip('/')!=path:continue
        for row in reversed(rows):
            if row.get('method','GET')!='GET' or not usable_body(row,archive,''):continue
            file=Path(archive)/row['key']
            if file.stat().st_size>8*1024*1024:continue
            try:payload=decode(file.read_bytes(),number)
            except (OSError,UnicodeError,ValueError,TypeError):continue
            if payload:return payload
    return None

def assets(payload,base):
    """Images/media referenced by JSONP question data load in the app document."""
    from html.parser import HTMLParser
    from urllib.parse import urljoin
    urls=set()
    class Images(HTMLParser):
        def handle_starttag(self,tag,attrs):
            values=dict(attrs)
            if tag in ('img','audio','video','source','iframe','image'):
                value=values.get('src') or values.get('href')
                if value:urls.add(urljoin(base,value))
    def walk(value,key=''):
        if isinstance(value,dict):
            for k,v in value.items():walk(v,k)
        elif isinstance(value,list):
            for row in value:walk(row,key)
        elif isinstance(value,str):
            if key in ('link','src','image','image_url') and value.strip():urls.add(urljoin(base,value))
            if '<' in value:Images().feed(value)
    walk(payload)
    return urls
