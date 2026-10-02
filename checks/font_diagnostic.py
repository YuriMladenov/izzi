"""Inspect font replay locally; no credentials, upstream requests, or archive writes."""
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server

mapping=server.load(server.URL_MAP_FILE,{})
paths=sys.argv[1:] or [
    '/DOS/1408736/profil/dist/izzi/fonts/IBMPlexSans/IBMPlexSans-'+weight+'.'+ext
    for weight in ('Regular','Bold') for ext in ('woff2','woff')
]
print('Font records in local archive:')
for url,records in mapping.items():
    path=urlparse(url).path
    if Path(path).suffix.lower() not in server.FONT_EXT:continue
    for r in records:
        f=server.ARCHIVE_DIR/(r.get('key') or '__missing__')
        try:
            with f.open('rb') as stream:magic=stream.read(4).hex()
            size=f.stat().st_size
        except OSError:magic='missing';size=0
        valid=bool(r.get('body_available') and r.get('key') and server.usable_font(r))
        print(f'{path}: status={r.get("status")} body={bool(r.get("body_available"))} size={size} magic={magic} usable={valid}')
print('\nRequested replay paths:')
missing=0
for path in paths:
    r=server.find(mapping,server.SOURCE_HOST,path,'',server.usable_font)
    if r:print('RESOLVED',path,'MIME='+server.replay_mime(path,r.get('content_type','')))
    else:
        missing+=1
        print('UNRESOLVED',path,'(no matching usable archived font body)')
raise SystemExit(bool(missing))
