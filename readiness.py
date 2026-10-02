"""Read-only readiness assessment using the same resolver as HTTP replay."""
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from replay_resolver import find,book_ids,_izzi_host,usable_body

LESSON=re.compile(r'^/DOS/(\d+)/(\d+)\.html$')
IMPORTANT={'.html','.js','.mjs','.css','.json','.svg','.png','.jpg','.jpeg','.webp','.gif',
           '.woff','.woff2','.ttf','.otf','.mp4','.mp3','.wav','.ogg','.m4a','.wasm','.pdf'}

def read_state(path,default,errors):
    if not path.exists():return default
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value,type(default)):raise ValueError('unexpected JSON root type')
        return value
    except (OSError,ValueError) as e:
        errors.append(f'{path.name}: {e}')
        return default

def usable_record(record,archive,ext):
    return usable_body(record,archive,ext)

def available(mapping,url,archive,book=None,complete_media=False):
    p=urlparse(url);ext=Path(p.path).suffix.lower()
    def usable(r):
        return usable_record(r,archive,ext)
    return find(mapping,p.hostname or 'bg.izzi.digital',p.path,p.query,usable,book) is not None

def related(url,record,bid):
    paths=[urlparse(url).path]+[urlparse(ref).path for ref in record.get('referers',[]) if isinstance(ref,str)]
    return any(bid in book_ids(p) for p in paths)

def important(url,observation,records):
    # Write-only API observations are not replay GET dependencies.
    if records and all(r.get('method','GET') not in ('GET','HEAD') for r in records):return False
    p=urlparse(url)
    if Path(p.path).suffix.lower() in IMPORTANT or p.path.startswith('/api/'):return True
    return any(str(ct).split(';')[0] in ('application/json','application/javascript','text/css','text/html')
               for ct in observation.get('content_types',[]))

def assess(root):
    root=Path(root);state=root/'state';archive=root/'archive';errors=[]
    mapping=read_state(state/'url_map.json',{},errors)
    for url,records in list(mapping.items()):
        if not isinstance(records,list) or any(not isinstance(r,dict) for r in records):
            errors.append('url_map: records must be arrays of objects');mapping.pop(url)
    metadata=read_state(state/'books.json',{},errors)
    observed=read_state(state/'capture_observed.json',{},errors).get('requests',{})
    session=read_state(state/'capture_session.json',{},errors)
    media=read_state(state/'media_map.json',{},errors).get('lessons',{})
    visits=session.get('visits',session.get('events',[]))
    if not isinstance(visits,list):errors.append('capture_session: visits must be a list');visits=[]
    if not isinstance(observed,dict):errors.append('capture_observed: requests must be an object');observed={}
    if not isinstance(media,dict):errors.append('media_map: lessons must be an object');media={}
    books={}
    for bid,meta in metadata.items():
        if not isinstance(meta,dict):errors.append('books: invalid book metadata');continue
        lessons=meta.get('lessons',{})
        if not isinstance(lessons,dict):errors.append('books: lessons must be an object');continue
        books.setdefault(str(bid),set()).update(str(lid) for lid in lessons)
    for url in set(mapping)|set(observed):
        p=urlparse(url);lesson=LESSON.match(p.path)
        if lesson and _izzi_host(p.hostname):books.setdefault(lesson[1],set()).add(lesson[2])
    for visit in visits:
        if isinstance(visit,dict) and visit.get('book') and visit.get('lesson'):
            books.setdefault(str(visit['book']),set()).add(str(visit['lesson']))
    for key in media:
        if re.fullmatch(r'\d+/\d+',key):
            bid,lid=key.split('/');books.setdefault(bid,set()).add(lid)
    results=[]
    for bid,lids in sorted(books.items()):
        starts={str(v['lesson']) for v in visits if isinstance(v,dict) and str(v.get('book'))==bid and v.get('kind')=='lesson-start' and v.get('lesson')}
        outcomes={}
        for v in visits:
            if isinstance(v,dict) and str(v.get('book'))==bid and v.get('lesson') and v.get('kind') in ('lesson-done','lesson-incomplete'):
                outcomes[str(v['lesson'])]=v['kind']
        dones={lid for lid,kind in outcomes.items() if kind=='lesson-done'}
        traversal_missing=lids-dones
        lesson_missing=[f'/DOS/{bid}/{lid}.html' for lid in sorted(lids)
                        if not available(mapping,f'https://bg.izzi.digital/DOS/{bid}/{lid}.html',archive,bid)]
        mapped=set();bad_mapping=[]
        for lid in lids:
            entry=media.get(f'{bid}/{lid}',{})
            if not isinstance(entry,dict) or not isinstance(entry.get('media',[]),list):
                errors.append('media_map: media entries must contain arrays');continue
            for row in entry.get('media',[]) if isinstance(entry,dict) else []:
                if not isinstance(row,dict) or not row.get('strict') or not row.get('url'):continue
                url=row['url']
                if book_ids(urlparse(url).path)-{bid}:bad_mapping.append(url)
                else:mapped.add(url)
        incomplete=[u for u in sorted(mapped) if not available(mapping,u,archive,bid,complete_media=Path(urlparse(u).path).suffix.lower()=='.mp4')]
        gaps=[];only304=[];warnings=[]
        urls=set(observed)|{u for u in mapping if bid in book_ids(urlparse(u).path)}
        for url in sorted(urls):
            row=observed.get(url,{})
            if not isinstance(row,dict) or not related(url,row,bid):continue
            p=urlparse(url)
            if not _izzi_host(p.hostname) or not important(url,row,mapping.get(url,[])):continue
            if available(mapping,url,archive,bid):continue
            statuses=set()
            for value in row.get('statuses',[]):
                try:statuses.add(int(value))
                except (TypeError,ValueError):pass
            for r in mapping.get(url,[]):
                if isinstance(r,dict) and r.get('status') is not None:
                    try:statuses.add(int(r['status']))
                    except (TypeError,ValueError):pass
            if statuses=={404}:warnings.append(url)
            else:
                gaps.append(url)
                if statuses=={304}:only304.append(url)
        failures=[]
        if traversal_missing:failures.append(f'lesson traversal incomplete ({len(dones & lids)}/{len(lids)})')
        if lesson_missing:failures.append(f'{len(lesson_missing)} lesson HTML body(s) unavailable')
        if gaps:failures.append(f'{len(gaps)} important resource(s) unavailable')
        if incomplete:failures.append(f'{len(incomplete)} mapped media resource(s) incomplete')
        if bad_mapping:failures.append(f'{len(bad_mapping)} cross-book media mapping(s) rejected')
        if errors:failures.append('state schema/read errors')
        label='INCOMPLETE' if failures else ('READY WITH WARNINGS' if warnings else 'READY')
        results.append(dict(book=bid,label=label,lessons=sorted(lids),starts=sorted(starts),done=sorted(dones & lids),
                            unfinished=sorted(traversal_missing),missing_lessons=lesson_missing,gaps=gaps,only304=only304,
                            mapped=sorted(mapped),incomplete_media=incomplete,bad_mapping=bad_mapping,warnings=warnings,failures=failures))
    # Errors discovered in later books must also prevent earlier READY labels.
    if errors:
        for result in results:
            result['label']='INCOMPLETE'
            if 'state schema/read errors' not in result['failures']:result['failures'].append('state schema/read errors')
    return dict(books=results,errors=errors)

def print_report(report):
    for error in report['errors']:print('STATE ERROR',error)
    if not report['books']:print('[INCOMPLETE] No books/lessons found; no archive readiness established.')
    for b in report['books']:
        print(f"\n[{b['label']}] BOOK {b['book']}")
        print('Lessons known:',len(b['lessons']))
        print('Traversal starts:',len(b['starts']))
        print('Traversal done:',len(b['done']),'/',len(b['lessons']))
        print('Missing lesson HTML:',len(b['missing_lessons']))
        print('304-only resources:',len(b['only304']))
        print('Mapped media URLs:',len(b['mapped']))
        print('Mapped media incomplete:',len(b['incomplete_media']))
        print('Missing important resources:',len(b['gaps']))
        print('Upstream 404 warnings:',len(b['warnings']))
        for category,items in [('UPSTREAM 404 WARNING',b['warnings']),('MISSING LESSON',b['missing_lessons']),
                               ('MISSING',b['gaps']),('INCOMPLETE MEDIA',b['incomplete_media']),('CROSS-BOOK MAP',b['bad_mapping'])]:
            for item in items:print(' ',category,item)
        for failure in b['failures']:print(' FAILURE',failure)
    print('\nReadiness covers known/observed resources; unobserved interactions still require local testing.')

def main():
    from config import ROOT
    report=assess(ROOT);print_report(report)
    return int(bool(report['errors']) or not report['books'] or any(b['label']=='INCOMPLETE' for b in report['books']))
