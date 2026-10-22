"""Match local books to usable original thumbnails in the captured catalogue."""
import json,re,html
from urllib.parse import urlsplit,quote
from replay_resolver import find,usable_body
SOURCE='bg.izzi.digital'

def publisher_name(*sources):
    for source in sources:
        value=source.get('publisher') if isinstance(source,dict) else None
        if isinstance(value,str) and value.strip():
            return re.sub(r'^Клет\s+България\s*[-–—]\s*(?=\S)','',value.strip(),flags=re.I)
    return ''

def grade_number(title,publication=None):
    publication=publication or {}
    grade=publication.get('grade',{})
    ordinals={'първи':1,'втори':2,'трети':3,'четвърти':4,'пети':5,'шести':6,'седми':7,'осми':8,'девети':9,'десети':10,'единадесети':11,'дванадесети':12}
    romans={'I':1,'II':2,'III':3,'IV':4,'V':5,'VI':6,'VII':7,'VIII':8,'IX':9,'X':10,'XI':11,'XII':12}
    labels=[title,publication.get('name','')]
    if isinstance(grade,dict):labels.extend([grade.get('name',''),grade.get('label','')])
    elif isinstance(grade,str):labels.append(grade)
    for label in labels:
        text=re.sub(r'<[^>]*>',' ',html.unescape(str(label or '')))
        match=re.search(r'\b(\d{1,2})\s*\.?\s*клас\b',text,re.I)
        if match and 1<=int(match[1])<=12:return int(match[1])
        match=re.search(r'\b('+'|'.join(ordinals)+r')\s+клас\b',text,re.I)
        if match:return ordinals[match[1].lower()]
        match=re.search(r'\b([IVX]+)\s*\.?\s*клас\b',text,re.I)
        if match and match[1].upper() in romans:return romans[match[1].upper()]
    value=grade.get('number') if isinstance(grade,dict) else None
    if isinstance(value,(int,str)) and not isinstance(value,bool) and str(value).isdigit() and 1<=int(value)<=12:return int(value)
    return 0

def catalog_covers(mapping,archive,books):
    result={str(bid):{'src':'','decoration':'','palette':'','grade':grade_number(book.get('title','')),'publisher':publisher_name(book)} for bid,book in books.items()}
    record=find(mapping,SOURCE,'/api/online-bookshelf-publications','',lambda row:usable_body(row,archive,'.json'))
    if not record:return result
    try:payload=json.loads((archive/record['key']).read_text(encoding='utf8'))
    except (OSError,ValueError):return result
    data=payload.get('data',{}) if isinstance(payload,dict) else {}
    if not isinstance(data,dict):return result
    resolved={}
    def thumbnail(thumbs,keys=('image1','image2')):
        if not isinstance(thumbs,dict):return ''
        for key in keys:
            value=thumbs.get(key)
            if not isinstance(value,str) or not value:continue
            parsed=urlsplit(value);host=parsed.hostname or SOURCE
            if host not in (SOURCE,'api.izzi.digital') or parsed.scheme not in ('','http','https'):continue
            path=parsed.path
            if not path.startswith('/'):continue
            key=(host,path,parsed.query)
            if key not in resolved:resolved[key]=bool(find(mapping,host,path,parsed.query,lambda row:usable_body(row,archive,'.png')))
            if resolved[key]:return '/__host__/'+host+quote(path,safe='/:%')+('?' + parsed.query if parsed.query else '')
        return ''
    def add(publication,group=None):
        if not isinstance(publication,dict):return
        bid=str(publication.get('dos_id',''))
        if bid not in result:return
        result[bid]['publisher']=publisher_name(publication,group,books[bid])
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
