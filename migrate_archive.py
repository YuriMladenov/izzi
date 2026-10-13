"""Offline, resumable archive layout migration. Originals remain until cleanup."""
import argparse,hashlib,json,os,re,shutil,socket,tempfile,time,uuid
from pathlib import Path
import archive_db
from archive_storage import shard_key
from archive_cleanup import contained
from import_har import load,save

def stamp(path):
    stat=path.stat();return [stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,stat.st_ino]

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.digest()

def auxiliary(state):
    for path in sorted(state.rglob('*.json')):
        if any(name in path.relative_to(state).parts for name in ('cleanup_trash','storage_backups')):continue
        if path.parent==state and (path.name in archive_db.NAMES or path.name=='storage_migration_report.json'):continue
        if not contained(state,path):raise ValueError('Symlink in archive state')
        yield path

def report(archive,state):
    archive=Path(archive);state=Path(state)
    if not archive_db.active(state/'url_map.json'):raise ValueError('First initialize the SQLite indexes')
    mapping=load(state/'url_map.json',{});files=[];stamps=[];missing=[]
    for rows in mapping.values():
        for row in rows:
            if row.get('body_available') and not (archive/row['key']).is_file():missing.append(row['key'])
    for dirname in ('blobs','assembled'):
        for path in sorted((archive/dirname).glob('*')):
            old=path.relative_to(archive).as_posix();new=shard_key(old)
            if new==old:continue
            target=archive/new
            if not contained(archive,path) or not contained(archive,target):raise ValueError('Unsafe archive path')
            if not path.is_file():continue
            files.append({'old':old,'new':new,'size':path.stat().st_size,'exists':target.exists()})
            stamps.append([old,stamp(path),stamp(target) if target.exists() else None])
    for path in auxiliary(state):
        json.loads(path.read_text(encoding='utf8'));stamps.append([path.relative_to(state).as_posix(),stamp(path)])
    revision=archive_db.revision(state/archive_db.DB_NAME)
    return {'files':files,'count':len(files),'copy_bytes':sum(r['size'] for r in files if not r['exists']),
            'missing':missing,'revision':revision,'fingerprint':hashlib.sha256(json.dumps([revision,stamps],sort_keys=True).encode()).hexdigest()}

def rewrite(value,keys):
    if isinstance(value,dict):return {k:rewrite(v,keys) for k,v in value.items()}
    if isinstance(value,list):return [rewrite(v,keys) for v in value]
    return keys.get(value,value) if isinstance(value,str) else value

def apply(archive,state,review):
    archive=Path(archive);state=Path(state);plan=report(archive,state)
    if review!=plan['fingerprint']:raise ValueError('Archive changed: generate a new report')
    if plan['missing']:raise ValueError('Referenced bodies are missing; repair before migration')
    keys={r['old']:r['new'] for r in plan['files']}
    if not keys:return {'moved':0,'backup':None}
    # Validate all conflicts before creating or updating anything.
    for row in plan['files']:
        if row['exists'] and digest(archive/row['old'])!=digest(archive/row['new']):raise ValueError('Conflicting destination: '+row['new'])
    if shutil.disk_usage(archive).free<plan['copy_bytes']+1024*1024:raise ValueError('Not enough disk space for verified copies')
    backup=state/'storage_backups'/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    backup.mkdir(parents=True,exist_ok=False)
    archive_db.backup(state,backup/archive_db.DB_NAME)
    aux=list(auxiliary(state))
    for path in aux:
        target=backup/(path.relative_to(state).as_posix()+'.bak');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    # Publish verified copies first. A crash at any point leaves old keys readable.
    for row in plan['files']:
        source=archive/row['old'];target=archive/row['new']
        if target.exists():continue
        target.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix='.migration-',dir=target.parent);os.close(fd)
        try:
            shutil.copy2(source,tmp)
            if digest(source)!=digest(Path(tmp)):raise ValueError('Copy verification failed')
            os.replace(tmp,target)
        finally:Path(tmp).unlink(missing_ok=True)
    mapping=load(state/'url_map.json',{})
    for url,rows in mapping.items():
        new=rewrite(rows,keys)
        if new!=rows:mapping[url]=new
    save(state/'url_map.json',mapping)
    books=load(state/'books.json',{})
    for key,value in books.items():
        new=rewrite(value,keys)
        if new!=value:books[key]=new
    save(state/'books.json',books)
    for path in aux:
        value=json.loads(path.read_text(encoding='utf8'));new=rewrite(value,keys)
        if new!=value:save(path,new)
    return {'moved':len(keys),'backup':str(backup)}

def port_busy(port):
    with socket.socket() as sock:
        sock.settimeout(.3);return sock.connect_ex(('127.0.0.1',port))==0

def main():
    from config import ARCHIVE_DIR,STATE_DIR,PORT,CAPTURE_PROXY_PORT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Apply after printing report; stop library/capture first')
    args=parser.parse_args()
    if port_busy(PORT) or port_busy(CAPTURE_PROXY_PORT):parser.error('Stop the library and capture proxy first')
    archive_db.initialize(STATE_DIR)
    result=report(ARCHIVE_DIR,STATE_DIR)
    out=STATE_DIR/'storage_migration_report.json';save(out,result)
    print('SQLite:',STATE_DIR/archive_db.DB_NAME)
    print('Files to distribute:',result['count'],'Additional copy bytes:',result['copy_bytes'],'Missing bodies:',len(result['missing']))
    print('Report:',out)
    if args.apply:
        done=apply(ARCHIVE_DIR,STATE_DIR,result['fingerprint']);print('Completed:',done)
        print('Original files retained. Run archive cleanup after checking the library.')
    else:print('Preview only. To apply: py migrate_archive.py --apply')
    return int(bool(result['missing']))
if __name__=='__main__':raise SystemExit(main())
