"""Explicit component binding; never guess replacements from other loaded applets."""
import re
import html,json
from urllib.parse import urlsplit

LESSON='/DOS/449527/449779.html'
BLOCK='8470030'
OLD='/datastore/15/publication/4033/files/2019/11/12/1573547071_1569840746_1569840539_1569406914_1567105534_Usp_vis_OK.ggb'
CURRENT='/datastore/15/publication/4033/files/2020/04/29/1588167488_b5_u104_usp_vis.ggb'

def normalize_path(path):
    if path.lower().endswith('.ggb'):
        return re.sub(r'^/DOS/\d+/(\d+/(?:publication/\d+|shared)/files/)',r'/datastore/\1',path)
    return path

def replacement(url,lesson,blocks):
    p=urlsplit(url);page=urlsplit(lesson)
    if page.hostname!='bg.izzi.digital' or page.path!=LESSON or BLOCK not in blocks:return None
    if p.hostname not in ('bg.izzi.digital','api.izzi.digital'):return None
    path=re.sub(r'^/DOS/\d+(?=/datastore/)','',normalize_path(p.path))
    if path==OLD:return 'https://bg.izzi.digital'+CURRENT
    return None

def prepare_html(data,lesson):
    """Repair only the identified component's config during offline replay."""
    from urllib.parse import urljoin
    if urlsplit(lesson).hostname!='bg.izzi.digital' or urlsplit(lesson).path!=LESSON:return data
    text=data.decode('utf8',errors='replace')
    def component(match):
        tag=match[0]
        if not re.search(r'\bblock-id\s*=\s*([\"\'])'+BLOCK+r'\1',tag):return tag
        def config(attr):
            try:
                obj=json.loads(html.unescape(attr[2]));file=obj['config']['filename'];changed=False
                for entry in (file,file.get('resource',{})):
                    for field in ('path','src'):
                        value=entry.get(field)
                        if isinstance(value,str) and replacement(urljoin(lesson,value),lesson,[BLOCK]):entry[field]=CURRENT;changed=True
                return attr[1]+html.escape(json.dumps(obj,ensure_ascii=False),quote=True)+attr[3] if changed else attr[0]
            except (ValueError,KeyError,TypeError,AttributeError):return attr[0]
        return re.sub(r'((?:v-bind:config|:config)\s*=\s*\')([^\']*)(\')',config,tag)
    return re.sub(r'<geogebra\b[^>]*>',component,text,flags=re.I).encode('utf8')
