"""Suggest catalogue labels from archived navigation without downloading anything."""
import json,re
from html.parser import HTMLParser
from import_har import clean_text,parse_dos_data
from replay_resolver import find,usable_body

def restore(book_id,rows,mapping,archive):
    inferred={};ranks={}
    class Navigation(HTMLParser):
        def __init__(self):super().__init__();self.modules=[];self.units=[]
        def handle_starttag(self,tag,attrs):
            attrs=dict(attrs)
            if tag=='breadcrumbs':
                try:items=json.loads(attrs.get(':items','[]'))
                except ValueError:return
                for item in items:
                    if item.get('systemType')=='module' or item.get('tmplLabel') in ('module','modul'):
                        self.modules.append(item)
                        if item.get('id'):ranks[str(item['id'])]=str(item.get('prettyPosition',''))
                        for sibling in item.get('siblings',[]):
                            if sibling.get('id'):ranks[str(sibling['id'])]=str(sibling.get('prettyPosition',''))
            if tag in ('units-list-item','unit-list-item'):
                try:item=json.loads(attrs.get(':item','{}'))
                except ValueError:return
                if item.get('id'):self.units.append((str(item['id']),attrs.get('position',''),attrs.get('title') or item.get('name','')))
    for row in rows:
        record=find(mapping,'bg.izzi.digital',row.get('path',''),'',lambda r:usable_body(r,archive,'.html'))
        if not record:continue
        try:data=(archive/record['key']).read_bytes();nav=Navigation();nav.feed(data.decode('utf8'))
        except (OSError,UnicodeError,ValueError):continue
        module=nav.modules[-1] if nav.modules else {}
        module_name=clean_text(module.get('name',''));module_id=str(module.get('id',''))
        dos=parse_dos_data(data)
        inferred.setdefault(row['id'],{'module':module_name,'title':clean_text(dos.get('title','')),'number':str(dos.get('prettyPosition','')),'module_id':module_id})
        for lid,number,title in nav.units:
            inferred[lid]={'module':module_name,'title':clean_text(title),'number':number,'module_id':module_id}
    result=[]
    for row in rows:
        item=dict(row);meta=inferred.get(row['id'],{})
        if meta.get('module'):item['module']=meta['module']
        if meta.get('title'):item['title']=meta['title']
        number=meta.get('number','')
        if re.fullmatch(r'\d+(?:\.\d+)*\.?',number):item['original_number']=number
        if item.get('original_number') and not item['title'].startswith(item['original_number']+' '):item['title']=item['original_number']+' '+item['title']
        item['_module_rank']=ranks.get(meta.get('module_id',''),'');result.append(item)
    def numeric(value):return tuple(int(x) for x in value.strip('.').split('.') if x.isdigit()) or (10**9,)
    return sorted(result,key=lambda item:(numeric(item['_module_rank']),numeric(item.get('original_number',''))))
