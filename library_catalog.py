"""Local presentation preferences; archive metadata remains unchanged."""
import threading,re
from import_har import load,save
LOCK=threading.Lock()

def ordered_lessons(book_id,book,session,preferences):
    lessons=book.get('lessons',{})
    order=[];captured={}
    for visit in session.get('visits',[]):
        lid=str(visit.get('lesson',''))
        if visit.get('kind')=='lesson-start' and str(visit.get('book'))==str(book_id) and lid in lessons and isinstance(visit.get('extra'),dict):
            captured.setdefault(lid,{}).update({key:value for key,value in visit['extra'].items() if value})
        if visit.get('kind')=='lesson-start' and str(visit.get('book'))==str(book_id) and lid in lessons and lid not in order:order.append(lid)
    settings=preferences.get(str(book_id),{})
    manual=settings.get('order',[])
    order=list(dict.fromkeys([str(x) for x in manual if str(x) in lessons]+order+list(lessons)))
    names=settings.get('names',{});hidden=set(settings.get('hidden',[]))
    rows=[]
    for lid in order:
        meta=captured.get(lid,{})
        title=names.get(lid) or meta.get('title') or lessons[lid].get('title','Урок '+lid)
        number=str(meta.get('number',''))
        if not re.fullmatch(r'\d+(?:\.\d+)*\.?',number):number=''
        if number and not title.startswith(number+' '):title=number+' '+title
        rows.append(dict(lessons[lid],id=lid,title=title,original_number=number,module=meta.get('module') or lessons[lid].get('module',''),hidden=lid in hidden))
    return rows

def update(path,book_id,lessons,form):
    known=set(lessons)
    rows=[];names={};hidden=[]
    for index,lid in enumerate(lessons):
        name=form.get('name_'+lid,[''])[0].strip()
        if len(name)>300:raise ValueError('title too long')
        rank=int(form.get('order_'+lid,[str(index+1)])[0])
        rows.append((rank,index,lid))
        if name:names[lid]=name
        if form.get('hidden_'+lid)==['on']:hidden.append(lid)
    if any(key not in {'name_'+x for x in known}|{'order_'+x for x in known}|{'hidden_'+x for x in known} for key in form):raise ValueError('unknown field')
    with LOCK:
        preferences=load(path,{})
        preferences[str(book_id)]={'order':[lid for _,_,lid in sorted(rows)],'names':names,'hidden':hidden}
        save(path,preferences)
