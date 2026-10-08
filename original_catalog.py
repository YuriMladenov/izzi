"""Replay the captured Bulgarian bookshelf without captured account data."""
import html,json,re
from urllib.parse import urlsplit
from replay_resolver import find,usable_body

PUBLIC_API={'/api/online-bookshelf-publications','/api/p/authapi/subjects','/api/p/authapi/school-groups'}

def public_entry(url):
    p=urlsplit(url)
    return (p.hostname=='bg.izzi.digital' and (p.path=='/' or p.path.startswith(('/_nuxt/','/DOS/','/assets/')) or p.path in PUBLIC_API)) or p.hostname in ('fonts.googleapis.com','fonts.gstatic.com')

def ready(mapping,archive):
    root=find(mapping,'bg.izzi.digital','/','',lambda r:usable_body(r,archive,'.html'))
    if not root:return None
    content=(archive/root['key']).read_text(encoding='utf8')
    scripts=re.findall(r'<script[^>]+src=["\']([^"\']+)',content)
    if not scripts or not all(find(mapping,'bg.izzi.digital',urlsplit(s).path,'',lambda r:usable_body(r,archive,'.js')) for s in scripts):return None
    if not find(mapping,'bg.izzi.digital','/api/online-bookshelf-publications','',lambda r:usable_body(r,archive,'.json')):return None
    return content

def local_shelf(payload,books):
    data=payload.get('data',{})
    def keep(pub):return str(pub.get('dos_id')) in books
    def local(pub):return dict(pub,dos_url='/__book__/'+str(pub['dos_id']))
    groups=[]
    for group in data.get('grouped',[]):
        pubs=[local(p) for p in group.get('publications',[]) if keep(p)]
        if pubs:groups.append(dict(group,publications=pubs))
    ungrouped=dict(data.get('ungrouped',{}))
    ungrouped['publications']=[local(p) for p in ungrouped.get('publications',[]) if keep(p)]
    return dict(payload,data=dict(data,grouped=groups,ungrouped=ungrouped))

def inject(content):
    # Imported HTML is an app shell, never a captured user profile.
    content=re.sub(r'<link\b[^>]*rel=["\'](?:icon|shortcut icon|apple-touch-icon|manifest|mask-icon)["\'][^>]*>','',content,flags=re.I)
    content=content.replace('</head>','<link rel="icon" href="data:,"></head>')
    content=re.sub(r'<script\b[^>]*src=["\'][^"\']*(?:googletagmanager|delivery/)[^"\']*["\'][^>]*>.*?</script>','',content,flags=re.I|re.S)
    sources=[('https://fonts.googleapis.com/','/__host__/fonts.googleapis.com/'),('https://fonts.gstatic.com/','/__host__/fonts.gstatic.com/')]
    for old,new in sources:content=content.replace(old,new)
    controls='<link rel="stylesheet" href="/__ui__/original.css"><script src="/__ui__/original.js" defer></script>'
    return content.replace('</head>',controls+'</head>')

def adapt_script(data):
    # The upstream market and locale are selected by hostname, not by API data.
    text=data.decode('utf8')
    text=text.replace('t.domain==window.location.host','t.domain=="bg.izzi.digital"').replace('}[window.location.hostname]', '}["bg.izzi.digital"]')
    text=re.sub(r'(\.defaultLocale=)[A-Za-z_$][\w$]*\.j\b',r'\1"bg"',text)
    return text.encode()
