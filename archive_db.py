"""SQLite resource/book indexes; legacy JSON is imported once and kept as backup."""
import json, re, sqlite3
from collections.abc import MutableMapping
from contextlib import closing,contextmanager
from pathlib import Path
from urllib.parse import urlparse, unquote
from replay_resolver import _canon_path

NAMES={'url_map.json':'resources','books.json':'books'}
DB_NAME='library.sqlite3'

def database(path):return Path(path).parent/DB_NAME

def active(path):return Path(path).name in NAMES and database(path).is_file()

@contextmanager
def connect(db):
    connection=None
    try:
        connection=sqlite3.connect(db,timeout=30)
        connection.execute('PRAGMA busy_timeout=30000')
        connection.execute('PRAGMA foreign_keys=ON')
        yield connection
    except sqlite3.Error as error:raise ValueError('SQLite index unavailable: '+str(error)) from error
    finally:
        if connection is not None:connection.close()

def encode(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'))

def columns(key,value,table):
    raw=encode(value)
    if table=='books':return key,raw
    p=urlparse(key);match=re.search(r'/DOS/\d+/\d+\.html$',unquote(p.path))
    return key,raw,_canon_path(p.path),match[0] if match else '',int(any(r.get('complete') for r in value))

def insert(c,table,key,value):
    if table=='books':c.execute('INSERT OR REPLACE INTO books(id,data) VALUES (?,?)',columns(key,value,table))
    else:c.execute('INSERT OR REPLACE INTO resources(url,data,canonical,lesson,complete) VALUES (?,?,?,?,?)',columns(key,value,table))

def initialize(state):
    """Transactional, idempotent import. No existing archive body or JSON is changed."""
    state=Path(state);state.mkdir(parents=True,exist_ok=True);db=state/DB_NAME
    with connect(db) as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.execute('BEGIN IMMEDIATE')
        try:
            c.execute('CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value INTEGER NOT NULL)')
            ready=c.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()
            if ready:
                if ready[0]!=1:raise ValueError('Unsupported SQLite schema')
                c.commit();return db
            data={}
            for name in NAMES:
                p=state/name;data[name]=json.loads(p.read_text(encoding='utf8')) if p.exists() else {}
                if not isinstance(data[name],dict):raise ValueError('Invalid index: '+name)
            for url,rows in data['url_map.json'].items():
                if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows):raise ValueError('Invalid resource record array')
                urlparse(url)
            if any(not isinstance(row,dict) for row in data['books.json'].values()):raise ValueError('Invalid book metadata')
            c.execute('CREATE TABLE resources(url TEXT PRIMARY KEY,data TEXT NOT NULL,canonical TEXT NOT NULL,lesson TEXT NOT NULL,complete INTEGER NOT NULL)')
            c.execute('CREATE INDEX resource_paths ON resources(canonical)')
            c.execute('CREATE INDEX resource_lessons ON resources(lesson)')
            c.execute('CREATE INDEX resource_complete ON resources(complete)')
            c.execute('CREATE TABLE books(id TEXT PRIMARY KEY,data TEXT NOT NULL)')
            for name,table in NAMES.items():
                for key,value in data[name].items():insert(c,table,key,value)
            c.executemany('INSERT INTO metadata VALUES (?,?)',[('schema',1),('revision',1)])
            c.commit()
        except Exception:c.rollback();raise
    return db

def revision(db):
    with connect(db) as c:
        if c.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()!=(1,):raise ValueError('Incomplete SQLite migration')
        return c.execute("SELECT value FROM metadata WHERE key='revision'").fetchone()[0]

class Index(MutableMapping):
    """Lazy mapping with per-key edits; save never rewrites the entire index."""
    def __init__(self,path):
        self.path=Path(path);self.db=database(path);self.table=NAMES[self.path.name];self.key='url' if self.table=='resources' else 'id'
        self.loaded={};self.original={};self.deleted=set();revision(self.db)
    def __getitem__(self,key):
        if key in self.deleted:raise KeyError(key)
        if key not in self.loaded:
            with connect(self.db) as c:row=c.execute(f'SELECT data FROM {self.table} WHERE {self.key}=?',(key,)).fetchone()
            self.original[key]=row[0] if row else None
            if row is None:raise KeyError(key)
            self.loaded[key]=json.loads(row[0])
        return self.loaded[key]
    def __setitem__(self,key,value):
        if key not in self.original:
            try:self[key]
            except KeyError:pass
        self.deleted.discard(key);self.loaded[key]=value
    def __delitem__(self,key):self[key];self.loaded.pop(key,None);self.deleted.add(key)
    def __iter__(self):
        with connect(self.db) as c:keys=[row[0] for row in c.execute(f'SELECT {self.key} FROM {self.table} ORDER BY rowid')]
        known=set(keys)
        return iter([key for key in keys if key not in self.deleted]+[key for key in self.loaded if key not in known and key not in self.deleted])
    def __len__(self):
        with connect(self.db) as c:count=c.execute(f'SELECT count(*) FROM {self.table}').fetchone()[0]
        return count-sum(self.original.get(key) is not None for key in self.deleted)+sum(self.original.get(key) is None for key in self.loaded)
    def items(self):
        # Stream scans without retaining every decoded resource in RAM.
        with connect(self.db) as c:
            for key,raw in c.execute(f'SELECT {self.key},data FROM {self.table} ORDER BY rowid'):
                if key not in self.deleted:yield key,self.loaded.get(key) if key in self.loaded else json.loads(raw)
        for key,value in self.loaded.items():
            if self.original.get(key) is None and key not in self.deleted:yield key,value
    def values(self):return (value for _,value in self.items())
    def candidates(self,column,value):
        if self.table!='resources':return ()
        with connect(self.db) as c:rows=c.execute(f'SELECT url,data FROM resources WHERE {column}=?',(value,)).fetchall()
        return [(url,urlparse(url),json.loads(raw)) for url,raw in rows]
    def replay_candidates(self,path):return self.candidates('canonical',path)
    def lesson_candidates(self,path):return self.candidates('lesson',path)
    def complete_items(self):return ((url,rows) for url,_,rows in self.candidates('complete',1))
    def commit(self):
        changed={key:value for key,value in self.loaded.items() if encode(value)!=self.original.get(key)}
        if not changed and not self.deleted:return
        with connect(self.db) as c:
            c.execute('BEGIN IMMEDIATE')
            for key in set(changed)|self.deleted:
                current=c.execute(f'SELECT data FROM {self.table} WHERE {self.key}=?',(key,)).fetchone()
                if (current[0] if current else None)!=self.original.get(key):
                    c.rollback();raise ValueError('Index entry changed concurrently; retry operation')
            for key in self.deleted:c.execute(f'DELETE FROM {self.table} WHERE {self.key}=?',(key,))
            for key,value in changed.items():insert(c,self.table,key,value)
            c.execute("UPDATE metadata SET value=value+1 WHERE key='revision'");c.commit()
        for key,value in changed.items():self.original[key]=encode(value)
        for key in self.deleted:self.original.pop(key,None)
        self.deleted.clear()

def write(path,value):
    if isinstance(value,Index):value.commit();return
    # Legacy bulk utilities replace the selected index transactionally.
    table=NAMES[Path(path).name]
    if not isinstance(value,dict):raise ValueError('Index root must be an object')
    with connect(database(path)) as c:
        c.execute('BEGIN IMMEDIATE');c.execute(f'DELETE FROM {table}')
        for key,row in value.items():insert(c,table,key,row)
        c.execute("UPDATE metadata SET value=value+1 WHERE key='revision'");c.commit()

def backup(state,target):
    """Consistent database backup, including committed WAL records."""
    with connect(Path(state)/DB_NAME) as c:
        # SQLite's connection context manager commits/rolls back without closing.
        with closing(sqlite3.connect(target)) as destination:c.backup(destination)

def update_entry(path,key,mutate,default):
    """Serialize a one-entry read/modify/write, including competing proxy writers."""
    table=NAMES[Path(path).name];column='url' if table=='resources' else 'id'
    with connect(database(path)) as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute(f'SELECT data FROM {table} WHERE {column}=?',(key,)).fetchone()
        old=row[0] if row else None
        value=json.loads(old) if old is not None else default
        mutate(value)
        if encode(value)!=old:
            insert(c,table,key,value);c.execute("UPDATE metadata SET value=value+1 WHERE key='revision'")
        c.commit()
