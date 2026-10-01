"""Read-only replay diagnostics for specific local resource paths."""
import sys
from pathlib import Path
from urllib.parse import urlparse,unquote
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server

mapping=server.load(server.URL_MAP_FILE,{})
paths=sys.argv[1:] or ['/__host__/api.izzi.digital/datastore/15/publication/1408736/pictures/2025/02/25/6a96b741e03ccf1442c42e990409eb55_2-3.png']
failed=0
for requested in paths:
    p=urlparse(requested);host=server.SOURCE_HOST;path=p.path
    if path.startswith('/__host__/'):
        host,tail=path[len('/__host__/'):].split('/',1);host=unquote(host);path='/'+tail
    ext=Path(path).suffix.lower()
    usable=server.usable_font if ext in server.FONT_EXT else server.usable_image
    print('REQUEST',requested)
    count=0
    for url,records in mapping.items():
        original=urlparse(url)
        if not server._izzi_host(original.hostname) or server._canon_path(original.path)!=server._canon_path(path):continue
        for record in records:
            count+=1
            blob=server.ARCHIVE_DIR/(record.get('key') or '__missing__')
            valid=bool(record.get('body_available') and record.get('key') and usable(record))
            print('MATCH',original.hostname,original.path,'status='+str(record.get('status')),
                  'body='+str(bool(record.get('body_available'))),'blob_exists='+str(blob.is_file()),'usable='+str(valid))
    result=server.find(mapping,host,path,p.query,usable)
    if result:print('RESOLVED',server.replay_mime(path,result.get('content_type','')))
    else:
        failed+=1
        print('UNRESOLVED','matching_records='+str(count),'(inspect missing bodies/blobs or captured origin errors above)')
raise SystemExit(bool(failed))
