"""Remove a book and its exclusive archive records, preserving shared blobs."""
import json,re,threading,shutil
from pathlib import Path
from urllib.parse import urlsplit
from import_har import load,save
from replay_resolver import book_ids
LOCK=threading.Lock()

def plan(book,state,archive):
    if not re.fullmatch(r'\d+',str(book)):raise ValueError('Invalid book ID')
    books=load(state/'books.json',{})
    if book not in books:raise ValueError('Unknown book')
    mapping=load(state/'url_map.json',{})
    session=load(state/'capture_session.json',{'visits':[]})
    visits=session.get('visits',[])
    mine={v.get('extra',{}).get('asset') for v in visits if str(v.get('book'))==book}
    others={v.get('extra',{}).get('asset') for v in visits if str(v.get('book'))!=book}
    links=load(state/'lesson_links.json',{})
    for root,entry in links.items():
        if root in mine:mine.update(entry.get('resources',[]))
        if root in others:others.update(entry.get('resources',[]))
    observed=load(state/'capture_observed.json',{'requests':{}})
    shared={url for url,row in observed.get('requests',{}).items() if any(book_ids(urlsplit(ref).path)-{book} for ref in row.get('referers',[]))}
    urls={url for url in mapping if ((book_ids(urlsplit(url).path)=={book} and (url not in shared or re.fullmatch('/DOS/'+book+r'/\d+\.html',urlsplit(url).path))) or (url in mine and url not in others and url not in shared and not (book_ids(urlsplit(url).path)&(set(books)-{book}))))}
    removed={r['key'] for url in urls for r in mapping[url] if r.get('key')}
    retained={r['key'] for url,rows in mapping.items() if url not in urls for r in rows if r.get('key')}
    retained_paths={(archive/key).resolve() for key in retained}
    import youtube_download
    own_videos={youtube_download.video_id(url) for url in mine if url}
    shared_videos={youtube_download.video_id(url) for url in others if url}
    files=[path for identifier in own_videos-shared_videos if identifier for path in (archive/'youtube').glob(identifier+'.*') if path.is_file() and path.resolve().is_relative_to(archive.resolve())]
    for key in removed-retained:
        path=(archive/key).resolve()
        if path not in retained_paths and path.is_relative_to(archive.resolve()) and path.is_file():files.append(path)
    ranges=[]
    for manifest in (state/'range_assembly').glob('*.json'):
        if re.fullmatch(r'[a-f0-9]{64}',manifest.stem) and load(manifest,{}).get('url') in urls:ranges.append(manifest)
    return {'ranges':ranges,'title':books[book].get('title',book),'urls':urls,'files':files,'bytes':sum(p.stat().st_size for p in files)}

def remove(book,state,archive):
    with LOCK:
        result=plan(book,state,archive)
        # Parse all relevant state before performing any mutation.
        mapping=load(state/'url_map.json',{});books=load(state/'books.json',{})
        prefs=load(state/'library_catalog.json',{});session=load(state/'capture_session.json',{'visits':[]})
        media=load(state/'media_map.json',{'lessons':{}});observed=load(state/'capture_observed.json',{'requests':{}})
        links=load(state/'lesson_links.json',{});active=load(state/'active_lesson.json',{})
        for url in result['urls']:mapping.pop(url,None);observed.get('requests',{}).pop(url,None);links.pop(url,None)
        books.pop(book);prefs.pop(book,None)
        session['visits']=[v for v in session.get('visits',[]) if str(v.get('book'))!=book]
        media['lessons']={key:value for key,value in media.get('lessons',{}).items() if not re.search(r'/DOS/'+book+r'/|^'+book+r'[:/]',key)}
        if str(active.get('book'))==book:active={}
        for name,data in [('books.json',books),('url_map.json',mapping),('library_catalog.json',prefs),('capture_session.json',session),('media_map.json',media),('capture_observed.json',observed),('lesson_links.json',links),('active_lesson.json',active)]:save(state/name,data)
        for path in result['files']:
            path.unlink(missing_ok=True)
            if path.parent.name=='youtube':
                for suffix in ('.json','.log'):(state/'youtube'/(path.name.split('.')[0]+suffix)).unlink(missing_ok=True)
        (state/'progress'/(book+'.jsonl')).unlink(missing_ok=True)
        for manifest in result['ranges']:
            work=manifest.with_suffix('')
            if work.is_dir() and not work.is_symlink():shutil.rmtree(work)
            manifest.unlink(missing_ok=True)
        # Historical misses must not restore deleted assets in the missing-resource list.
        log=state/'missing_resources.jsonl'
        if log.exists():
            lines=[]
            for line in log.read_text(encoding='utf8').splitlines():
                try:row=json.loads(line)
                except ValueError:lines.append(line);continue
                url='https://'+row.get('host','')+row.get('path','')
                if book_ids(row.get('path',''))!={book} and url not in result['urls']:lines.append(line)
            log.write_text(''.join(line+'\n' for line in lines),encoding='utf8')
        return result
