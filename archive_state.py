"""Read-only replay snapshots, invalidated by atomic replacement or file changes."""
import json,threading,re
from pathlib import Path
from urllib.parse import urlparse,unquote
from replay_resolver import _canon_path
import archive_db
LOCK=threading.RLock();CACHE={}

class ReplayMap(dict):
    def __init__(self,data):super().__init__(data);self.index=None;self.lessons=None;self.lock=threading.Lock()
    def prepare(self):
        with self.lock:
            if self.index is not None:return
            index={};lessons={}
            for url,records in self.items():
                try:p=urlparse(url)
                except ValueError:continue
                entry=(url,p,records);index.setdefault(_canon_path(p.path),[]).append(entry)
                match=re.search(r'/DOS/\d+/\d+\.html$',unquote(p.path))
                if match:lessons.setdefault(match[0],[]).append(entry)
            self.index=index;self.lessons=lessons
    def replay_candidates(self,path):self.prepare();return self.index.get(path,())
    def lesson_candidates(self,path):self.prepare();return self.lessons.get(path,())

def signature(path):
    stat=path.stat();return stat.st_mtime_ns,stat.st_ctime_ns,stat.st_size,stat.st_ino

def load(path,default):
    path=Path(path).resolve()
    if archive_db.active(path):
        # SQLite may wait for I/O; do not block all other HTTP worker threads.
        stamp=('sqlite',signature(archive_db.database(path)),archive_db.revision(archive_db.database(path)))
        with LOCK:
            if path in CACHE and CACHE[path][0]==stamp:return CACHE[path][1]
        value=archive_db.Index(path)
        with LOCK:CACHE[path]=(stamp,value)
        return value
    with LOCK:
        try:stamp=signature(path)
        except FileNotFoundError:CACHE.pop(path,None);return default
        if path in CACHE and CACHE[path][0]==stamp:return CACHE[path][1]
        for _ in range(3):
            with path.open(encoding='utf8') as stream:value=json.load(stream)
            after=signature(path)
            if after==stamp:
                if path.name=='url_map.json' and isinstance(value,dict):value=ReplayMap(value)
                CACHE[path]=(stamp,value);return value
            stamp=after
        raise OSError('Archive state changed while being read')
