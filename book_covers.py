"""Match local books to usable original thumbnails in the captured catalogue."""
import json,re
from urllib.parse import urlsplit,quote
from replay_resolver import find,usable_body
SOURCE='bg.izzi.digital'

def grade_number(title,publication=None):
    grade=(publication or {}).get('grade',{})
    value=grade.get('number') if isinstance(grade,dict) else None
    if isinstance(value,int) and 1<=value<=12:return value
    match=re.search(r'\b(\d{1,2})\s*\.?\s*клас\b',title,re.I)
    return int(match.group(1)) if match else 0

def catalog_covers(mapping,archive,books):
    result={str(bid):{'src':'','decoration':'','palette':'','grade':grade_number(book.get('title',''))} for bid,book in books.items()}
    record=find(mapping,SOURCE,'/api/online-bookshelf-publications','',lambda row:usable_body(row,archive,'.json'))
    if not record:return result
    try:payload=json.loads((archive/record['key']).read_text(encoding='utf8'))
    except (OSError,ValueError):return result
    data=payload.get('data',{}) if isinstance(payload,dict) else {}
    if not isinstance(data,dict):return result
    def thumbnail(thumbs,keys=('image1','image2')):
        if not isinstance(thumbs,dict):return ''
        for key in keys:
            value=thumbs.get(key)
            if not isinstance(value,str) or not value:continue
            parsed=urlsplit(value);host=parsed.hostname or SOURCE
            if host not in (SOURCE,'api.izzi.digital') or parsed.scheme not in ('','http','https'):continue
            path=parsed.path
            if not path.startswith('/'):continue
            row=find(mapping,host,path,parsed.query,lambda row:usable_body(row,archive,'.png'))
            if row:return '/__host__/'+host+quote(path,safe='/:%')+('?' + parsed.query if parsed.query else '')
        return ''
    def add(publication,group=None):
        if not isinstance(publication,dict):return
        bid=str(publication.get('dos_id',''))
        if bid not in result:return
        thumbs=publication.get('thumbs')
        if not thumbnail(thumbs):thumbs=(group or {}).get('thumbs')
        cover=thumbnail(thumbs,('image1',)) or thumbnail(thumbs)
        decoration=thumbnail(thumbs,('image2',))
        result[bid]['decoration']=decoration if decoration!=cover else ''
        palette=publication.get('dos_class') or (group or {}).get('dos_class','')
        result[bid]['palette']=palette if isinstance(palette,str) and re.fullmatch(r'palette(?:[0-9]|[1-4][0-9]|5[0-2])',palette) else ''
        if cover:result[bid]['src']=cover
        result[bid]['grade']=grade_number(books[bid].get('title',''),publication)
    for group in data.get('grouped',[]):
        if isinstance(group,dict):
            for publication in group.get('publications',[]):add(publication,group)
    ungrouped=data.get('ungrouped',{})
    if isinstance(ungrouped,dict):
        for publication in ungrouped.get('publications',[]):add(publication)
    return result
