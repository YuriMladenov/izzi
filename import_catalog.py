"""Import only bookshelf assets and public catalogue responses from a HAR."""
import sys,hashlib,mimetypes
from pathlib import Path
from urllib.parse import urlsplit
from config import ARCHIVE_DIR,URL_MAP_FILE
from import_har import load,save,body
from original_catalog import public_entry

def main():
    if len(sys.argv)!=2:print('Usage: py import_catalog.py catalogue.har');return 1
    har=load(Path(sys.argv[1]),{});mapping=load(URL_MAP_FILE,{})
    count=0
    for entry in har.get('log',{}).get('entries',[]):
        request=entry.get('request',{});response=entry.get('response',{})
        url=request.get('url','')
        if request.get('method')!='GET' or response.get('status')!=200 or not public_entry(url):continue
        raw=body(response.get('content',{}))
        if not raw:continue
        mime=response.get('content',{}).get('mimeType','')
        ext=Path(urlsplit(url).path).suffix or mimetypes.guess_extension(mime.split(';')[0]) or '.bin'
        key='blobs/'+hashlib.sha256(raw).hexdigest()+ext[:12]
        target=ARCHIVE_DIR/key;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        record={'key':key,'content_type':mime,'status':200,'body_available':True,'method':'GET','size':len(raw),'decoded':True,'source':'catalog_har'}
        rows=mapping.setdefault(urlsplit(url)._replace(fragment='').geturl(),[])
        if not any(r.get('key')==key for r in rows):rows.append(record)
        count+=1
    save(URL_MAP_FILE,mapping)
    print('Imported catalogue resources:',count,'(account APIs, cookies and request headers excluded)')
    return 0
if __name__=='__main__':raise SystemExit(main())
