"""Conservative archive inventory and reversible cleanup; never edits resource indexes."""
import hashlib,json,re,shutil,threading,uuid
from pathlib import Path
from time import time as now
from urllib.parse import urlsplit
from import_har import save,load
from collections.abc import Mapping
import archive_db
from archive_storage import assembled_key
from replay_resolver import find,usable_body,complete_body
LOCK=threading.RLock()

def read(path):
    with path.open(encoding='utf8') as stream:return json.load(stream)

def contained(root,path):
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):return False
    for parent in path.absolute().parents:
        if parent==root.absolute():break
        if parent.is_symlink():return False
    return True

def report(archive,state,include_incomplete=False):
    archive=Path(archive);state=Path(state)
    using_db=archive_db.active(state/'url_map.json')
    mapping=load(state/'url_map.json',{}) if using_db else read(state/'url_map.json')
    books=load(state/'books.json',{}) if using_db else read(state/'books.json')
    if not isinstance(mapping,Mapping) or not isinstance(books,Mapping):raise ValueError('Невалиден индекс: почистването е блокирано.')
    if books and not mapping:raise ValueError('Празен URL индекс при налични учебници: почистването е блокирано.')
    protected=set();stamps=[]
    if using_db:
        db=state/archive_db.DB_NAME
        if not contained(state,db):raise ValueError('Невалиден път на SQLite индекса.')
        stat=db.stat();stamps.append(('sqlite',archive_db.revision(db),stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,stat.st_ino))
    def protect(value):
        if isinstance(value,dict):
            for item in value.values():protect(item)
        elif isinstance(value,list):
            for item in value:protect(item)
        elif isinstance(value,str):
            p=Path(value)
            if not p.is_absolute() and value.startswith(('blobs/','assembled/','youtube/')):
                p=archive/p
                if not contained(archive,p):raise ValueError('Невалиден път в индекса.')
                protected.add(p.resolve())
    for path in sorted(state.rglob('*.json')):
        if 'cleanup_trash' in path.relative_to(state).parts:continue
        if path.parent==state and (path.name=='storage_migration_report.json' or (using_db and path.name in archive_db.NAMES)):continue
        if not contained(state,path):raise ValueError('Символни връзки в state: почистването е блокирано.')
        data=read(path);stat=path.stat();stamps.append((str(path.relative_to(state)),stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns))
        protect(data)
    protect(dict(books.items()))
    for rows in mapping.values():
        if not isinstance(rows,list):raise ValueError('Невалиден url_map.json.')
        for row in rows:
            if not isinstance(row,dict) or (not isinstance(row.get('key'),str) or not row.get('key')):raise ValueError('Невалиден ресурсен запис.')
            p=archive/row['key']
            if not contained(archive,p):raise ValueError('Ресурс извън archive: почистването е блокирано.')
            protected.add(p.resolve())
            if row.get('body_available') and not p.is_file():raise ValueError('Липсва файл, посочен в индекса. Първо поправи архива.')
    selected={};preserved=[];needed_parts=set()
    def item(path,root,category):
        base=archive if root=='archive' else state
        if not contained(base,path) or not path.is_file():return None
        stat=path.stat()
        return {'root':root,'path':path.relative_to(base).as_posix(),'category':category,'size':stat.st_size,'mtime':stat.st_mtime_ns,'ctime':stat.st_ctime_ns,'inode':stat.st_ino}
    def add(path,root,category):
        entry=item(path,root,category)
        if entry:selected[(root,entry['path'])]=entry
    # Range manifests protect their assembled result, even before registration finished.
    for manifest in sorted((state/'range_assembly').glob('*.json')):
        data=read(manifest)
        if not isinstance(data,dict):raise ValueError('Невалиден range manifest.')
        url=data.get('url','');total=data.get('total')
        if not isinstance(data,dict) or not isinstance(url,str) or not isinstance(total,int) or total<=0 or not isinstance(data.get('ranges'),list):raise ValueError('Невалиден MP4 range manifest.')
        for part in data['ranges']:
            if not isinstance(part,list) or len(part)!=3 or not isinstance(part[0],int) or not isinstance(part[1],int) or not 0<=part[0]<=part[1]<total or not isinstance(part[2],str):raise ValueError('Невалиден диапазон в range manifest.')
        identity=hashlib.sha256(url.encode()).hexdigest()
        if manifest.stem!=identity:raise ValueError('Неразпознат range manifest: почистването е блокирано.')
        for final in (archive/'assembled'/(identity+'.mp4'),archive/assembled_key(identity)):protected.add(final.resolve())
        parsed=urlsplit(url)
        row=find(mapping,parsed.hostname or '',parsed.path,parsed.query,lambda r:usable_body(r,archive,'.mp4') and (r.get('status')==200 or complete_body(r)))
        completed=bool(row and (archive/row['key']).stat().st_size==total)
        if completed:
            with (archive/row['key']).open('rb') as stream:completed=b'ftyp' in stream.read(64)
        if completed:
            stat=(archive/row['key']).stat();stamps.append(('archive/'+row['key'],stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns))
        elif not include_incomplete:
            for _,_,name in data['ranges']:
                match=re.search(r'(?:^|/)range_assembly/([a-f0-9]{64}/[0-9]+-[0-9]+\.part)$',name.replace('\\','/'))
                if match:needed_parts.add((state/'range_assembly'/match[1]).resolve())
        folder=state/'range_assembly'/identity
        for part in folder.glob('*.part'):
            entry=item(part,'state','Недовършени видео части')
            if completed:add(part,'state','Части на готови видеа')
            elif include_incomplete:add(part,'state','Недовършени видео части')
            elif entry:preserved.append(entry)
        if completed or include_incomplete:add(manifest,'state','Range метаданни')
    known={p.stem for p in (state/'range_assembly').glob('*.json')}
    for part in (state/'range_assembly').rglob('*.part'):
        if part.parent.name in known:continue
        entry=item(part,'state','Части без manifest')
        if include_incomplete:add(part,'state','Части без manifest')
        elif entry:preserved.append(entry)
    for dirname in ('blobs','assembled'):
        for path in (archive/dirname).rglob('*'):
            if path.is_file() and re.fullmatch(r'[a-f0-9]{64}\.[A-Za-z0-9]+',path.name) and path.resolve() not in protected:
                stat=path.stat()
                if now()-max(stat.st_mtime,stat.st_ctime)<300:
                    entry=item(path,'archive','Нов файл: запазен за минимум 5 минути')
                    if entry:preserved.append(entry)
                else:add(path,'archive','Неизползвани архивни файлове')
    # YouTube files are outside the URL map; preserve all completed videos.
    for path in (archive/'youtube').glob('*'):
        if not path.name.endswith(('.part','.ytdl','.tmp')):continue
        identifier=path.name.split('.')[0];meta=state/'youtube'/(identifier+'.json')
        ready=meta.is_file() and read(meta).get('state')=='ready' and any((archive/'youtube'/(identifier+ext)).is_file() for ext in ('.mp4','.webm'))
        if ready:add(path,'archive','Временни части на готови YouTube видеа')
        elif include_incomplete:add(path,'archive','Недовършени YouTube части')
        else:
            entry=item(path,'archive','Недовършени YouTube части')
            if entry:preserved.append(entry)
    for key,entry in list(selected.items()):
        if entry['root']=='state' and (state/entry['path']).resolve() in needed_parts:
            preserved.append({**entry,'category':'Части, нужни на недовършено видео'});del selected[key]
    files=sorted(selected.values(),key=lambda x:(x['root'],x['path']))
    if using_db and stamps[0][1]!=archive_db.revision(state/archive_db.DB_NAME):raise ValueError('Индексът се промени. Генерирай нов отчет.')
    fingerprint=hashlib.sha256(json.dumps([stamps,files,include_incomplete],sort_keys=True).encode()).hexdigest()
    return {'files':files,'preserved':preserved,'bytes':sum(x['size'] for x in files),'fingerprint':fingerprint,'include_incomplete':include_incomplete}

def quarantine(archive,state,review,include_incomplete=False):
    with LOCK:
        result=report(archive,state,include_incomplete)
        if result['fingerprint']!=review:raise ValueError('Архивът е променен. Генерирай нов отчет.')
        batch=uuid.uuid4().hex;folder=state/'cleanup_trash'/batch;folder.mkdir(parents=True)
        manifest={'files':result['files']};save(folder/'manifest.json',manifest)
        for entry in result['files']:
            source=(archive if entry['root']=='archive' else state)/entry['path']
            target=folder/entry['root']/entry['path'];target.parent.mkdir(parents=True,exist_ok=True)
            shutil.move(str(source),str(target))
        return batch

def batches(state):
    result=[]
    for folder in sorted((state/'cleanup_trash').glob('*')):
        if not re.fullmatch(r'[a-f0-9]{32}',folder.name) or not contained(state,folder):continue
        files=[p for p in folder.rglob('*') if p.is_file() and p.name!='manifest.json']
        result.append({'id':folder.name,'count':len(files),'bytes':sum(p.stat().st_size for p in files)})
    return result

def restore(archive,state,batch):
    with LOCK:
        if not re.fullmatch(r'[a-f0-9]{32}',batch):raise ValueError('Невалидна папка за възстановяване.')
        folder=state/'cleanup_trash'/batch
        if not contained(state,folder):raise ValueError('Невалиден път.')
        manifest=read(folder/'manifest.json');moves=[]
        for entry in manifest['files']:
            if entry['root'] not in ('archive','state'):raise ValueError('Невалиден manifest.')
            base=archive if entry['root']=='archive' else state
            source=folder/entry['root']/entry['path'];target=base/entry['path']
            if not contained(folder,source) or not contained(base,target):raise ValueError('Невалиден път.')
            if not source.is_file():continue
            stat=source.stat()
            if stat.st_size!=entry['size'] or stat.st_mtime_ns!=entry['mtime']:raise ValueError('Файлът за възстановяване е променен.')
            if target.exists():raise ValueError('Вече има файл на оригиналното място. Възстановяването е блокирано.')
            moves.append((source,target))
        for source,target in moves:target.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(source),str(target))
        return len(moves)

def trash_report(state,batch):
    if not re.fullmatch(r'[a-f0-9]{32}',batch):raise ValueError('Невалидна папка.')
    folder=state/'cleanup_trash'/batch
    if not contained(state,folder) or not (folder/'manifest.json').is_file():raise ValueError('Невалидна папка.')
    entries=[]
    for path in sorted(folder.rglob('*')):
        if not contained(folder,path):raise ValueError('Невалиден път в папката за възстановяване.')
        if path.is_file():
            stat=path.stat();entries.append((path.relative_to(folder).as_posix(),stat.st_size,stat.st_mtime_ns))
    return {'id':batch,'count':len(entries),'bytes':sum(e[1] for e in entries),'fingerprint':hashlib.sha256(json.dumps(entries).encode()).hexdigest()}

def purge(state,batch,review):
    with LOCK:
        result=trash_report(state,batch)
        if result['fingerprint']!=review:raise ValueError('Папката е променена. Генерирай нов отчет.')
        shutil.rmtree(state/'cleanup_trash'/batch)
