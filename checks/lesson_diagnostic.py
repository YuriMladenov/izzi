"""Read-only lesson record diagnostics; never prints HTML bodies or URL queries."""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config import ROOT,ARCHIVE_DIR,URL_MAP_FILE,SOURCE_HOST
from replay_resolver import _canon_path,_izzi_host,find,usable_body,complete_range

def main():
    print('PROJECT',ROOT)
    print('URL MAP',URL_MAP_FILE)
    try:
        mapping=json.loads(URL_MAP_FILE.read_text(encoding='utf-8'))
        if not isinstance(mapping,dict):raise ValueError('URL map root must be an object')
    except (OSError,ValueError) as error:
        print('STATE ERROR',str(error));return 1
    paths=sys.argv[1:] or ['/DOS/1408736/1408782.html','/DOS/1408736/1408803.html']
    failed=0
    for requested in paths:
        path=urlparse(requested).path
        print('\nREQUEST',path);count=0
        for url,records in mapping.items():
            p=urlparse(url)
            if not _izzi_host(p.hostname) or _canon_path(p.path)!=_canon_path(path):continue
            if not isinstance(records,list):print('INVALID RECORD ARRAY');continue
            for row in records:
                if not isinstance(row,dict):print('INVALID RECORD');continue
                count+=1;key=row.get('key');blob=ARCHIVE_DIR/key if isinstance(key,str) and key else None
                actual=blob.stat().st_size if blob and blob.is_file() else None
                good=usable_body(row,ARCHIVE_DIR,'.html')
                reasons=[]
                if not row.get('body_available'):reasons.append('body_unavailable')
                if not key:reasons.append('no_blob_key')
                elif actual is None:reasons.append('blob_missing')
                if row.get('size') is not None and actual is not None and row['size']!=actual:reasons.append('size_mismatch')
                if row.get('status',200) not in (200,206):reasons.append('non_success_status')
                if row.get('status')==206 and not good:reasons.append('206_not_verified_complete')
                print('RECORD',p.hostname,p.path,'status='+str(row.get('status')),
                      'method='+str(row.get('method')),'body='+str(bool(row.get('body_available'))),
                      'decoded='+str(row.get('decoded')),'declared_size='+str(row.get('size')),
                      'blob_size='+str(actual),'full_range='+str(complete_range(row,actual)),
                      'usable='+str(good),'reason='+(','.join(reasons) or 'none'))
        result=find(mapping,SOURCE_HOST,path,'',lambda row:usable_body(row,ARCHIVE_DIR,'.html'))
        if result:print('RESOLVED text/html')
        else:failed+=1;print('UNRESOLVED matching_records='+str(count))
    return int(bool(failed))

if __name__=='__main__':raise SystemExit(main())
