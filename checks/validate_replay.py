"""Validate replay against isolated synthetic data, never real archives."""
import hashlib
import json
import sys
import tempfile
import threading
import urllib.request
import urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
import server
import assembled_media
import media_mapping

failures = []
with tempfile.TemporaryDirectory(prefix='izzi-validation-') as td:
    root = Path(td)
    archive = root / 'archive'
    state = root / 'state'
    archive.mkdir()
    state.mkdir()
    for mod in (server, assembled_media):
        mod.ARCHIVE_DIR = archive
        mod.URL_MAP_FILE = state / 'url_map.json'
    server.STATE_DIR = state
    server.BOOKS_FILE = state / 'books.json'
    server.PROGRESS_DIR = state / 'progress'
    media_mapping.P = state / 'media_map.json'
    mapping = {}
    def add(url, body, content_type, **extra):
        key = hashlib.sha256(body).hexdigest()
        (archive / key).write_bytes(body)
        mapping[url] = [dict(key=key, content_type=content_type, status=200,
                             body_available=True, method='GET', decoded=True,
                             size=len(body), **extra)]
    add('https://bg.izzi.digital:443/DOS/1408736/1408788.html',
        b'<html><body>fixture lesson</body></html>', 'text/html')
    add('https://bg.izzi.digital/datastore/test.css', b'body{color:red}', 'text/css')
    add('https://bg.izzi.digital/datastore/test.js', b'window.fixture=true;', 'application/javascript')
    add('https://bg.izzi.digital/datastore/test.woff2', b'wOF2' + bytes(128), 'application/octet-stream')
    font_path='/profil/dist/izzi/fonts/IBMPlexSans/IBMPlexSans-Regular.woff2'
    font_body=b'wOF2'+bytes(128)
    add('https://bg.izzi.digital'+font_path,font_body,'application/octet-stream')
    # A newer missing or captured HTML error record must not hide a usable font.
    mapping['https://bg.izzi.digital'+font_path].extend([
        dict(mapping['https://bg.izzi.digital'+font_path][0],key='missing-font'),
        dict(mapping['https://bg.izzi.digital'+font_path][0],key='font-error'),
    ])
    (archive/'font-error').write_bytes(b'<html>error</html>')
    add('https://bg.izzi.digital/profil/invalid.woff2',b'<html>error</html>','text/html')
    image_path='/datastore/15/publication/1408736/pictures/2025/02/25/6a96b741e03ccf1442c42e990409eb55_2-3.png'
    image_body=b'\x89PNG\r\n\x1a\nfixture'
    add('https://bg.izzi.digital'+image_path,image_body,'image/png')
    add('https://api.izzi.digital'+image_path,b'<html>Not found</html>','text/html')
    mapping['https://api.izzi.digital'+image_path][0]['status']=404
    add('https://bg.izzi.digital/datastore/upstream_extracted.png',b'origin 404','text/plain')
    mapping['https://bg.izzi.digital/datastore/upstream_extracted.png'][0]['status']=404
    video = bytes(range(256)) * 8
    add('https://bg.izzi.digital/datastore/test.mp4', video, 'video/mp4',
        source='assembled_ranges', complete=True)
    add('https://bg.izzi.digital/datastore/normal.mp4', video, 'video/mp4')
    add('https://bg.izzi.digital/datastore/incomplete.mp4', video[:256], 'video/mp4')
    mapping['https://bg.izzi.digital/datastore/incomplete.mp4'][0].update(
        status=206, content_range='bytes 0-255/2048')
    # A partial capture must never displace the assembled body for the same URL.
    mapping['https://bg.izzi.digital/datastore/test.mp4'].append(
        mapping['https://bg.izzi.digital/datastore/incomplete.mp4'][0].copy())
    (state / 'url_map.json').write_text(json.dumps(mapping))
    (state / 'books.json').write_text(json.dumps({'1408736': {'title': 'Fixture book',
        'lessons': {'1408788': {'id':'1408788', 'title':'Fixture lesson',
                              'path':'/DOS/1408736/1408788.html'}}}}))
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.H)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    checks = [('/', 'text/html', None),
              ('/DOS/1408736/1408788.html', 'text/html', None),
              ('/DOS/1408736/datastore/test.css', 'text/css', b'body{color:red}'),
              ('/datastore/test.js', 'application/javascript', b'window.fixture=true;'),
              ('/datastore/test.woff2', 'font/woff2', b'wOF2' + bytes(128)),
              ('/DOS/1408736'+font_path,'font/woff2',font_body),
              ('/__offline__/youtube-api.js','application/javascript',b'/* YouTube player API is unavailable in offline replay. */'),
              ('/__host__/api.izzi.digital'+image_path,'image/png',image_body),
              ('/datastore/test.mp4', 'video/mp4', video[:1024]),
              ('/DOS/1408736/datastore/test.mp4', 'video/mp4', video[:1024]),
              ('/datastore/test.mp4?cachebust=1', 'video/mp4', video[:1024]),
              ('/datastore/normal.mp4', 'video/mp4', video[:1024])]
    range_checks = [
        ('HEAD', '/datastore/test.mp4', 'bytes=0-1023', 206, b'', 'bytes 0-1023/2048'),
        ('GET', '/datastore/test.mp4', None, 200, video, None),
        ('GET', '/datastore/test.mp4', 'bytes=1024-2047', 206, video[1024:], 'bytes 1024-2047/2048'),
        ('GET', '/datastore/test.mp4', 'bytes=-256', 206, video[-256:], 'bytes 1792-2047/2048'),
        ('GET', '/datastore/test.mp4', 'bytes=2048-', 416, None, 'bytes */2048'),
        ('GET', '/datastore/incomplete.mp4', 'bytes=0-1023', 409, b'Incomplete captured media range', None),
        ('GET', '/datastore/missing.mp4', 'bytes=0-1023', 404, b'Not captured', None),
        ('GET', '/datastore/upstream_extracted.png', None, 404, b'origin 404', None),
        ('GET', '/profil/invalid.woff2', None, 404, b'Not captured', None),
        ('GET', '/__host__/api.izzi.digital'+image_path.replace('/1408736/','/9999999/'), None, 404, b'Not captured', None),
    ]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        for path, mime, expected in checks:
            try:
                req = urllib.request.Request(f'http://127.0.0.1:{httpd.server_port}{path}',
                    headers={'Range':'bytes=0-1023'} if mime=='video/mp4' else {})
                with opener.open(req, timeout=5) as r:
                    body = r.read()
                    assert r.status == (206 if mime=='video/mp4' else 200)
                    assert r.headers['Content-Type'].startswith(mime)
                    if expected is not None: assert body == expected
                    if path.endswith('.html'): assert b'fixture lesson' in body
                    if mime=='video/mp4':
                        assert r.headers['Content-Range']=='bytes 0-1023/2048'
                        assert r.headers['Content-Length']=='1024'
                        assert r.headers['Accept-Ranges']=='bytes'
                        if 'normal.mp4' not in path:
                            assert r.headers['X-IZZI-Replay']=='complete-media-range'
                print('PASS', path)
            except Exception as e:
                failures.append(path)
                print('FAIL', path, repr(e))
        for method, path, range_value, status, expected, content_range in range_checks:
            label=f'{method} {path} {range_value}'
            try:
                req=urllib.request.Request(f'http://127.0.0.1:{httpd.server_port}{path}',
                    method=method, headers={'Range':range_value} if range_value else {})
                try:
                    response=opener.open(req, timeout=5)
                except urllib.error.HTTPError as e:
                    response=e
                with response as r:
                    body=r.read()
                    assert r.code==status, (r.code, status)
                    assert r.headers.get('Content-Range')==content_range
                    if expected is not None: assert body==expected
                    if status in (200,206):
                        assert r.headers['Content-Type']=='video/mp4'
                        assert r.headers['Accept-Ranges']=='bytes'
                        assert int(r.headers['Content-Length'])==(1024 if method=='HEAD' else len(body))
                print('PASS',label)
            except Exception as e:
                failures.append(label)
                print('FAIL',label,repr(e))
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()
print(f'Synthetic replay checks: {len(checks)+len(range_checks)-len(failures)} passed, {len(failures)} failed')
raise SystemExit(bool(failures))
