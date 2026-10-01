"""Durable local request journal; does not emulate upstream progress semantics."""
import base64
import json
import os
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

LOCK=threading.Lock()
MAX_WRITE=10*1024*1024

def book_from_context(referer,path):
    for value in (path,referer):
        match=re.search(r'/DOS/(\d+)(?:/|$)',urlparse(value).path)
        if match:return match[1]
    return 'general'

def append(directory,method,path,referer,raw,content_type=''):
    bid=book_from_context(referer,path)
    entry={'time':time.strftime('%Y-%m-%d %H:%M:%S'),'method':method,
           'path':path,'referer':urlparse(referer)._replace(query='',fragment='').geturl(),
           'body':raw.decode('utf-8',errors='replace'),'body_base64':base64.b64encode(raw).decode('ascii'),
           'size':len(raw),'content_type':content_type}
    directory=Path(directory)
    with LOCK:
        directory.mkdir(parents=True,exist_ok=True)
        with (directory/(bid+'.jsonl')).open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(entry,ensure_ascii=False)+'\n')
            stream.flush();os.fsync(stream.fileno())
    return bid

def summarize(directory):
    books=[]
    for path in sorted(Path(directory).glob('*.jsonl')):
        item={'book':path.stem,'records':0,'invalid_lines':0,'legacy_records':0,'bytes':0,'endpoints':{}}
        with path.open(encoding='utf-8',errors='replace') as stream:
            for line in stream:
                if not line.strip():continue
                try:
                    row=json.loads(line)
                    if not isinstance(row,dict):raise ValueError('invalid row')
                    if 'body_base64' in row:
                        raw=base64.b64decode(row['body_base64'],validate=True)
                        if len(raw)!=row.get('size'):raise ValueError('size mismatch')
                        item['bytes']+=len(raw)
                    else:item['legacy_records']+=1
                    endpoint=str(row.get('method','?'))+' '+urlparse(row.get('path','')).path
                    item['endpoints'][endpoint]=item['endpoints'].get(endpoint,0)+1
                    item['records']+=1
                except (ValueError,TypeError,KeyError):item['invalid_lines']+=1
        books.append(item)
    return {'books':books,'records':sum(b['records'] for b in books),
            'invalid_lines':sum(b['invalid_lines'] for b in books),
            'note':'Local request journal only; server-side progress restoration is not implemented.'}
